# -*- coding: utf-8 -*-
"""그림 도구 테스트. sample.py 의 그림을 임시 폴더에 그려 한도·팔레트·밝은 면 검사를 보고, 색 상수가 편집기 테마와 같은지 봄.

실행: python -m unittest tests.test_journey_art
Pillow 가 없으면 그리기 테스트를, PyQt6 가 없으면 테마 비교를 건너뜀. 창을 띄우지 않음.
"""
import os

os.environ.setdefault("STUDY_NODE_PROBE", "0")

import contextlib  # noqa: E402
import io  # noqa: E402
import shutil  # noqa: E402
import sys  # noqa: E402
import tempfile  # noqa: E402
import types  # noqa: E402
import unittest  # noqa: E402
from unittest import mock  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import tools.journey_art as journey_art  # noqa: E402

try:
    from PIL import Image
    from tools.journey_art import draw, render, sample
except ImportError:
    Image = draw = render = sample = None

try:
    from gui import theme
except ImportError:
    theme = None


def fake_module(name, *fns):
    """@figure 함수를 담은 가짜 던전 스크립트. 이름이 d02 면 render 가 그림 이름의 앞부분을 2- 로 봄."""
    module = types.ModuleType(name)
    for fn in fns:
        setattr(module, fn.__name__, fn)
    return module


@unittest.skipUnless(theme, "PyQt6 없음")
class ThemeColorsTest(unittest.TestCase):
    def test_colors_match_editor_tokens(self):
        for name, value in journey_art.COLORS.items():
            self.assertEqual(value, theme.EDITOR[name], name)


@unittest.skipUnless(Image, "Pillow 없음")
class DrawTest(unittest.TestCase):
    def test_palette_is_57_distinct_colors_with_every_editor_color(self):
        self.assertEqual(len(draw.PALETTE), 57)
        self.assertEqual(len(set(draw.PALETTE)), 57)
        for value in journey_art.COLORS.values():
            self.assertIn(draw.rgb(value), draw.PALETTE)
        self.assertIn(draw.shade("def", 0.5), draw.PALETTE)
        self.assertIn(draw.shade("def", 0.75), draw.PALETTE)
        with self.assertRaises(ValueError):
            draw.shade("def", 0.3)

    def test_color_accepts_token_hex_tuple_and_none(self):
        self.assertEqual(draw.color("ink"), draw.rgb("#e0e8f0"))
        self.assertEqual(draw.color("#102030"), (16, 32, 48))
        self.assertEqual(draw.color((1, 2, 3)), (1, 2, 3))
        self.assertIsNone(draw.color(None))
        with self.assertRaises(ValueError):
            draw.color("muted")

    def test_figure_rejects_bad_name_width_and_frame_time(self):
        with self.assertRaises(ValueError):
            draw.Figure("fig1", 560, 300)
        with self.assertRaises(ValueError):
            draw.Figure("1-1a", journey_art.LIMITS["width"] + 1, 300)
        fig = draw.Figure("1-1a", 560, 300)
        with self.assertRaises(ValueError):
            fig.frame(journey_art.LIMITS["ms_min"] - 1)
        with self.assertRaises(ValueError):
            fig.frame(journey_art.LIMITS["ms_max"] + 1)
        self.assertEqual(fig.frame(1400).im.size, (560 * journey_art.SCALE, 300 * journey_art.SCALE))
        self.assertEqual(fig.kind, "png")
        fig.frame(1400)
        self.assertEqual(fig.kind, "gif")

    def test_bright_check_catches_ink_box_and_passes_text_and_cells(self):
        canvas = draw.Canvas(560, 200)
        canvas.text(20, 20, "장부 줄 lo mid 12", size=16)
        canvas.text(20, 50, "굵은 제목 ABC 123", size=20, bold=True)
        rects = canvas.cells(20, 90, [1, 2, 3, 5], marks={1: draw.shade("def", 0.5)})
        canvas.pointer(draw.mid_x(rects[0]), 90, "l")
        canvas.number_board(300, 90, "답", 42)
        canvas.tag(420, 90, "+3")
        self.assertEqual(draw.bright_runs(canvas.im), 0)
        canvas.box(100, 140, 150, 50, fill="ink", outline=None)
        self.assertGreater(draw.bright_runs(canvas.im), 0)

    def test_cells_and_grid_draw_hatch_under_the_value(self):
        def inside(rect):
            x, y, w, h = rect
            region = canvas.im.crop(tuple(round(v * draw.SCALE) for v in (x + 2, y + 2, x + w - 2, y + h - 2)))
            return set(c for _, c in region.getcolors(region.width * region.height))

        canvas = draw.Canvas(200, 120)
        missing, ink = draw.rgb(journey_art.COLORS["missing"]), draw.rgb(journey_art.COLORS["ink"])
        rects = canvas.cells(10, 10, [7, 8], hatch={1: "missing"})
        self.assertNotIn(missing, inside(rects[0]))
        self.assertTrue({missing, ink} <= inside(rects[1]))  # 빗금과 값이 같이 보임
        rows = canvas.grid(10, 60, [[1, 2]], hatch={(0, 0): "missing"})
        self.assertTrue({missing, ink} <= inside(rows[0][0]))
        self.assertNotIn(missing, inside(rows[0][1]))

    def test_quantized_frame_only_uses_palette_colors(self):
        canvas = draw.Canvas(200, 100)
        canvas.text(10, 10, "가장자리가 부드러운 글자", size=18)
        canvas.arrow(10, 60, 180, 90, "def")
        self.assertTrue(draw.outside_palette(canvas.im))  # 글자 가장자리의 중간색
        self.assertEqual(draw.outside_palette(draw.quantize(canvas.im)), [])

    def test_figures_lists_decorated_functions_by_name(self):
        found = draw.figures(sample)
        self.assertEqual([item[0] for item in found], ["0-1a", "0-1b"])
        self.assertEqual(found[0][1:3], (560, 300))
        self.assertTrue(callable(found[0][3]))


@unittest.skipUnless(Image, "Pillow 없음")
class RenderTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="journey_art_test_")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def test_sample_figures_meet_limits_and_share_the_palette(self):
        rows = render.render(sample, self.tmp, check=True)
        by_kind = {row["kind"]: row for row in rows}
        self.assertEqual(sorted(by_kind), ["gif", "png"])
        self.assertEqual(len(rows), 2)
        for row in rows:
            self.assertEqual(row["problems"], [], row)
        gif, png = by_kind["gif"], by_kind["png"]
        self.assertEqual(gif["frames"], 3)
        self.assertEqual(png["frames"], 1)
        self.assertLessEqual(gif["bytes"], journey_art.LIMITS["gif_bytes"])
        self.assertLessEqual(png["bytes"], journey_art.LIMITS["png_bytes"])
        logical = {name: width for name, width, _, _ in draw.figures(sample)}
        for row in rows:
            self.assertEqual(row["width"], logical[row["name"]] * journey_art.SCALE)
            self.assertEqual(os.path.basename(row["path"]), "%s.%s" % (row["name"], row["kind"]))
        with Image.open(gif["path"]) as im:
            self.assertEqual(im.n_frames, 3)
            for i in range(3):
                im.seek(i)
                self.assertEqual(im.info["duration"], 1400)
                self.assertEqual(draw.outside_palette(im), [])
                self.assertEqual(draw.bright_runs(im), 0)
        with Image.open(png["path"]) as im:
            self.assertEqual(draw.outside_palette(im), [])

    def test_render_only_named_figures_and_rejects_unknown_names(self):
        rows = render.render(sample, self.tmp, names=["0-1b"])
        self.assertEqual([row["name"] for row in rows], ["0-1b"])
        self.assertEqual(os.listdir(self.tmp), ["0-1b.png"])
        with self.assertRaises(ValueError):
            render.render(sample, self.tmp, names=["0-9z"])

    def test_render_flags_frame_count_name_prefix_and_size_limits(self):
        @draw.figure("1-1a", 200, 100)
        def many(fig):
            for i in range(journey_art.LIMITS["frames"] + 1):
                fig.frame(1000).caption(str(i))

        rows = render.render(fake_module("d02", many), self.tmp)
        problems = rows[0]["problems"]
        self.assertTrue(any("프레임" in p for p in problems), problems)
        self.assertTrue(any("2-" in p for p in problems), problems)
        with mock.patch.dict(journey_art.LIMITS, {"gif_bytes": 100, "total_bytes": 200}):
            rows = render.render(fake_module("d01", many), self.tmp)
            self.assertTrue(any("크기" in p for p in rows[0]["problems"]), rows[0]["problems"])
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertGreater(render.report(rows, self.tmp), 0)
            self.assertIn("합계가 한도를 넘습니다", out.getvalue())

    def test_check_flags_bright_box_and_colors_outside_the_palette(self):
        @draw.figure("1-2a", 300, 120)
        def bright(fig):
            fig.frame().box(40, 20, 150, 50, fill="ink", outline=None)

        rows = render.render(fake_module("d01", bright), self.tmp, check=True)
        self.assertTrue(any("밝은 면" in p for p in rows[0]["problems"]), rows[0]["problems"])
        self.assertEqual(render.render(fake_module("d01", bright), self.tmp)[0]["problems"], [])  # --check 없이는 한도만 봄
        stray = os.path.join(self.tmp, "1-3a.png")
        Image.new("RGB", (100, 60), (1, 2, 3)).save(stray)
        self.assertTrue(any("팔레트" in p for p in render.inspect(stray, check=True)["problems"]))
        self.assertEqual(render.inspect(stray)["problems"], [])

    def test_inspect_flags_frame_time_outside_the_range(self):
        frames = [Image.new("RGB", (40, 40), value) for value in ((0, 0, 0), (200, 200, 200))]  # 같은 프레임이 이어지면 Pillow 가 하나로 합침
        path = os.path.join(self.tmp, "1-4a.gif")
        frames[0].save(path, save_all=True, append_images=frames[1:], duration=[1400, 3000], loop=0)
        problems = render.inspect(path)["problems"]
        self.assertTrue(any("3000ms" in p for p in problems), problems)

    def test_main_writes_table_and_returns_zero_for_sample(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = render.main(["sample", "--out", self.tmp, "--check"])
        self.assertEqual(code, 0, out.getvalue())
        text = out.getvalue()
        self.assertIn("0-1a", text)
        self.assertIn("0-1b", text)
        self.assertIn("통과", text)
        self.assertEqual(sorted(os.listdir(self.tmp)), ["0-1a.gif", "0-1b.png"])

    def test_main_rejects_bad_arguments(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertNotEqual(render.main([]), 0)
            self.assertNotEqual(render.main(["sample"]), 0)  # 던전이 아니면 --out 이 있어야 함
            self.assertNotEqual(render.main(["sample", "0-9z", "--out", self.tmp]), 0)
            self.assertNotEqual(render.main(["d99", "--out", self.tmp]), 0)
        self.assertEqual(os.listdir(self.tmp), [])

    def test_sample_main_writes_into_the_given_folder(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(sample.main([self.tmp]), 0)
        self.assertEqual(sorted(os.listdir(self.tmp)), ["0-1a.gif", "0-1b.png"])

    def test_name_prefix(self):
        self.assertEqual(render.name_prefix("tools.journey_art.d01"), "1-")
        self.assertEqual(render.name_prefix("d12"), "12-")
        self.assertIsNone(render.name_prefix("tools.journey_art.sample"))


if __name__ == "__main__":
    unittest.main()
