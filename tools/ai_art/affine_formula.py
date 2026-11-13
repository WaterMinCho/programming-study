# -*- coding: utf-8 -*-
"""평행이동의 각 행 계산과 역조회를 2D 그림으로 만듦."""
import hashlib
from pathlib import Path

from tools.ai_art import read_manifest, write_manifest
from tools.ai_art.al01 import font, text

ROOT = Path(__file__).resolve().parents[2]


def frames():
    """입력·첫째 행·둘째 행·역조회 네 장을 그림. 숫자는 순수 계산으로 확인함."""
    from PIL import Image, ImageDraw
    assert [sum(a * b for a, b in zip(row, (2, 1, 1))) for row in ((1, 0, 3), (0, 1, 2))] == [5, 3]
    assert (5 - 3, 3 - 2) == (2, 1)
    out = []
    for stage in range(4):
        image = Image.new("RGB", (1120, 600), "white")
        d = ImageDraw.Draw(image)
        text(d, (36, 22), "평행이동의 입력과 출력", 38, bold=True)
        text(d, (36, 80), "2×3 행렬  ×  숫자 3개  →  출력 좌표 2개", 30, "#2563eb")
        text(d, (70, 148), "x에 곱함    y에 곱함    1에 곱함", 28)
        for row, values in enumerate(((1, 0, 3), (0, 1, 2))):
            for col, value in enumerate(values):
                x, y = 65 + col * 145, 198 + row * 82
                d.rounded_rectangle((x, y, x + 122, y + 67), 8,
                                    fill="#dbeafe" if stage == row + 1 else "#f3f4f6", outline="#9ca3af", width=2)
                d.text((x + 61, y + 34), str(value), font=font(34, True), anchor="mm", fill="#1f2937")
        text(d, (510, 222), "×", 40)
        for row, label in enumerate(("2  ← x", "1  ← y", "1  ← 붙인 1")):
            text(d, (575, 175 + row * 65), label, 32, "#2563eb" if row == 2 else "#1f2937", True)
        text(d, (64, 376), ("입력 모양 (3,) · 마지막 1은 이동을 더하는 자리입니다.",
                            "x′ = 1×2 + 0×1 + 3×1 = 5",
                            "y′ = 0×2 + 1×1 + 2×1 = 3",
                            "역조회: x = 5 − 3 = 2, y = 3 − 2 = 1")[stage], 31, "#2563eb", True)
        text(d, (64, 439), ("첫째 행은 x′, 둘째 행은 y′를 만듭니다.",
                            "출력의 첫째 값은 x′입니다.",
                            "출력 [5, 3] · 모양 (2,)",
                            "이동만 있는 같은 행렬에서 원본 (2, 1)을 찾습니다.")[stage], 30)
        # 격자는 같은 축척으로 그림. 영상의 y는 아래로 증가함.
        x0, y0, scale = 870, 190, 30
        d.line((x0, y0, x0 + 180, y0), fill="#1f2937", width=3)
        d.line((x0, y0, x0, y0 + 150), fill="#1f2937", width=3)
        d.polygon(((x0 + 180, y0), (x0 + 168, y0 - 5), (x0 + 168, y0 + 5)), fill="#1f2937")
        d.polygon(((x0, y0 + 150), (x0 - 5, y0 + 138), (x0 + 5, y0 + 138)), fill="#1f2937")
        text(d, (1055, 172), "x", 27)
        text(d, (840, 326), "y", 27)
        text(d, (842, 155), "0", 24)
        for px, py in ((2, 1), (5, 3)):
            xx, yy = x0 + px * scale, y0 + py * scale
            d.ellipse((xx-6, yy-6, xx+6, yy+6), fill="#2563eb")
            text(d, (xx-38, yy+12), "(%d,%d)" % (px, py), 24)
        text(d, (64, 530), "2D 점 · 붙인 1을 높이로 그리지 않습니다.", 27, "#6b7280")
        out.append(image)
    return out


def main():
    """이 그림만 저장하고 기존 그림의 바이트와 목록은 보존함."""
    from PIL import Image
    images = frames()
    palette_source = Image.new("RGB", (1120, 600 * len(images)))
    for n, image in enumerate(images):
        palette_source.paste(image, (0, n * 600))
    palette = palette_source.quantize(colors=64, method=Image.Quantize.MEDIANCUT)
    images = [im.quantize(palette=palette, dither=Image.Dither.NONE) for im in images]
    target = ROOT / "ai/learn/al02/assets/a2d-4.gif"
    images[0].save(target, save_all=True, append_images=images[1:], duration=2200, loop=0, disposal=1, optimize=True)
    manifest = read_manifest()
    manifest["files"]["learn/al02/assets/a2d-4.gif"] = {"sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
        "script": "tools/ai_art/affine_formula.py", "fn": "frames"}
    write_manifest(manifest)


if __name__ == "__main__":
    main()
