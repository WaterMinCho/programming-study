# -*- coding: utf-8 -*-
"""입체 도식 도우미 tools/ai_art/iso.py 의 좌표 계산을 확인함. Pillow 없이 돎.

실행: python -m unittest tests.test_ai_art_iso
"""
import os
import sys
import unittest
from math import hypot

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import ai_art  # noqa: E402
from tools.ai_art import iso  # noqa: E402


def close(test, a, b, places=6):
    test.assertEqual(len(a), len(b))
    for p, q in zip(a, b):
        test.assertAlmostEqual(p[0], q[0], places)
        test.assertAlmostEqual(p[1], q[1], places)


class RuleTest(unittest.TestCase):
    def test_request_values(self):
        self.assertEqual(("#f8fafc", "#e2e8f0", "#cbd5e1"), tuple(iso.FACES["normal"][k] for k in ("top", "left", "right")))
        self.assertEqual(("#bfdbfe", "#dbeafe", "#93c5fd"), tuple(iso.FACES["new"][k] for k in ("top", "left", "right")))
        self.assertEqual("#2563eb", iso.FACES["strong"]["right"])
        self.assertEqual((16, -12), iso.LAYER)
        self.assertEqual((1.5, 1.2, 1.5, (3, 3)), (iso.LINE, iso.DIVIDE, iso.DASH_W, iso.DASH))
        self.assertTrue(2.5 <= iso.ARROW_W <= 3)
        self.assertAlmostEqual(1.0, hypot(*iso.DEPTH))
        self.assertAlmostEqual(iso.LAYER[1] / float(iso.LAYER[0]), iso.DEPTH[1] / iso.DEPTH[0])

    def test_every_color_in_fixed_palette(self):
        colors = [v for style in iso.FACES.values() for v in style.values() if v]
        colors += [v for tone in iso.TONES.values() for v in tone]
        for value in colors:
            self.assertIn(value, ai_art.FIXED)

    def test_states_tell_apart(self):
        new, seen, todo = iso.FACES["new"], iso.FACES["seen"], iso.FACES["todo"]
        self.assertNotEqual(new["top"], seen["top"])
        self.assertNotEqual(new["line"], seen["line"])
        self.assertIsNone(todo["top"])
        with self.assertRaises(ValueError):
            iso.faces_of("current")
        self.assertTrue(iso.card_style("blue", "todo")[5])
        self.assertGreater(iso.card_style("red", "new")[2], iso.card_style("red", "seen")[2])
        with self.assertRaises(ValueError):
            iso.card_style("pink", "new")
        with self.assertRaises(ValueError):
            iso.card_style("blue", "strong")
        solid = iso.card_style("green", "solid")
        self.assertEqual((iso.TONES["green"][1], iso.TONES["green"][1], iso.WHITE, True), solid[:2] + solid[3:5])


class GridTest(unittest.TestCase):
    def setUp(self):
        self.grid = iso.Grid((100, 50), cell=60, thick=10)

    def test_point_moves(self):
        g = self.grid
        self.assertEqual((100, 50), g.point(0, 0))
        x, y = g.point(0, 1)
        self.assertAlmostEqual(100 + 60 * 3 ** 0.5 / 2, x)
        self.assertAlmostEqual(80, y)
        x, y = g.point(1, 0)
        self.assertAlmostEqual(100 - 60 * 3 ** 0.5 / 2, x)
        self.assertAlmostEqual(80, y)
        self.assertAlmostEqual(g.point(1, 1, 25)[1], g.point(1, 1)[1] - 25)

    def test_top_diamond(self):
        back, right, front, left = self.grid.top(0, 0)
        self.assertAlmostEqual(back[0], front[0])
        self.assertAlmostEqual(left[1], right[1])
        self.assertAlmostEqual(back[0] - left[0], right[0] - back[0])
        self.assertAlmostEqual(front[1] - back[1], 2 * self.grid.b)
        self.assertAlmostEqual(40, back[1])

    def test_faces_share_edges(self):
        f = self.grid.faces(1, 2, lift=5)
        back, right, front, left = f["top"]
        self.assertEqual([left, front], f["left"][:2])
        self.assertEqual([front, right], f["right"][:2])
        self.assertAlmostEqual(f["left"][2][1] - front[1], 10)
        self.assertEqual(f["left"][2], f["right"][3])
        self.assertAlmostEqual(self.grid.point(1, 2, 15)[1], back[1])

    def test_order_back_to_front(self):
        order = self.grid.order(3, 3)
        self.assertEqual(9, len(set(order)))
        self.assertEqual((0, 0), order[0])
        self.assertEqual((2, 2), order[-1])
        sums = [r + c for r, c in order]
        self.assertEqual(sorted(sums), sums)

    def test_center_and_bounds(self):
        g = self.grid
        cx, cy = g.center(0, 0)
        back, right, front, left = g.top(0, 0)
        self.assertAlmostEqual((back[0] + front[0]) / 2, cx)
        self.assertAlmostEqual((back[1] + front[1]) / 2, cy)
        x0, y0, x1, y1 = g.bounds(3, 3)
        self.assertAlmostEqual(100 - 3 * g.a, x0)
        self.assertAlmostEqual(100 + 3 * g.a, x1)
        self.assertAlmostEqual(40, y0)
        self.assertAlmostEqual(50 + 6 * g.b, y1)

    def test_fits_diamond(self):
        a, b = self.grid.a, self.grid.b
        self.assertTrue(iso.fits_diamond(20, 18, a, b))
        self.assertFalse(iso.fits_diamond(2 * a, 4, a, b))
        self.assertFalse(iso.fits_diamond(10, 2 * b, a, b))


class ObliqueTest(unittest.TestCase):
    def setUp(self):
        self.grid = iso.Oblique((100, 50), cell=80, thick=10)

    def test_rows_stay_level(self):
        g = self.grid
        self.assertEqual((100, 50), g.point(0, 0))
        self.assertEqual((180, 50), g.point(0, 1))
        self.assertEqual((60, 90), g.point(1, 0))
        self.assertEqual((40, 20), (g.a, g.b))
        back, right, front, left = g.top(1, 1)
        self.assertAlmostEqual(back[1], right[1])
        self.assertAlmostEqual(left[1], front[1])
        self.assertAlmostEqual(front[1] - back[1], g.dy)

    def test_faces_and_order(self):
        g = self.grid
        f = g.faces(0, 0)
        self.assertAlmostEqual(f["left"][0][1], f["left"][1][1])
        self.assertEqual([(0, 0), (0, 1), (0, 2), (1, 0), (1, 1), (1, 2)], g.order(2, 3))
        x0, y0, x1, y1 = g.bounds(3, 3)
        self.assertEqual((100 - 3 * 40, 40, 100 + 3 * 80, 50 + 3 * 40), (x0, y0, x1, y1))
        for up, down in iso.window_lines(g, 0, 1, 2, 2, 100):
            self.assertAlmostEqual(up[0], down[0])
            self.assertAlmostEqual(down[1] - up[1], 100)


class BoxTest(unittest.TestCase):
    def test_faces(self):
        f = iso.box_faces(10, 100, 40, 80, 20)
        self.assertEqual([(10, 100), (50, 100), (50, 180), (10, 180)], f["left"])
        close(self, [(10, 100), (50, 100), (66, 88), (26, 88)], f["top"])
        close(self, [(50, 100), (66, 88), (66, 168), (50, 180)], f["right"])

    def test_anchors(self):
        a = iso.box_anchors(10, 100, 40, 80, 20)
        self.assertAlmostEqual(38, a["above"][0])
        self.assertAlmostEqual(88, a["above"][1])
        self.assertEqual((30, 180), a["below"])
        self.assertEqual((30, 140), a["center"])
        close(self, [(10, 88), (66, 180)], [a["bbox"][:2], a["bbox"][2:]])

    def test_zero_depth_is_flat(self):
        a = iso.box_anchors(0, 0, 40, 30, 0)
        self.assertEqual((0, 0, 40, 30), a["bbox"])

    def test_stack_offsets(self):
        self.assertEqual([(2, 32, -24), (1, 16, -12), (0, 0, 0)], iso.stack_offsets(3))
        self.assertEqual([(0, 0, 0)], iso.stack_offsets(1))
        self.assertEqual([(1, 22, -22), (0, 0, 0)], iso.stack_offsets(2, (22, -22)))

    def test_stack_anchors(self):
        a = iso.stack_anchors(100, 200, 80, 80, 3, 10)
        close(self, [(100, 200 - 24 - 6), (100 + 80 + 32 + 8, 280)], [a["bbox"][:2], a["bbox"][2:]])
        self.assertAlmostEqual((a["bbox"][0] + a["bbox"][2]) / 2, a["above"][0])
        self.assertAlmostEqual(a["bbox"][1], a["above"][1])
        self.assertEqual((140, 280), a["below"])


class WindowTest(unittest.TestCase):
    def test_lines_drop_straight_down(self):
        g = iso.Grid((300, 200), cell=64, thick=14)
        lines = iso.window_lines(g, 0, 0, 2, 2, 120)
        self.assertEqual(4, len(lines))
        for up, down in lines:
            self.assertAlmostEqual(up[0], down[0])
            self.assertAlmostEqual(down[1] - up[1], 120)
        close(self, [down for _, down in lines], g.top(0, 0, 14, 2, 2))


class CurveTest(unittest.TestCase):
    def test_straight_and_bent(self):
        self.assertEqual([(0, 0), (100, 0)], iso.bezier((0, 0), (100, 0)))
        pts = iso.bezier((0, 0), (100, 0), 0.2, steps=10)
        self.assertEqual(11, len(pts))
        self.assertEqual((0, 0), pts[0])
        close(self, [(100, 0)], pts[-1:])
        self.assertLess(pts[5][1], 0)
        self.assertAlmostEqual(-10, pts[5][1])
        self.assertGreater(iso.bezier((0, 0), (100, 0), -0.2, steps=10)[5][1], 0)

    def test_trim(self):
        close(self, [(0, 0), (90, 0)], iso.trim([(0, 0), (100, 0)], 10))
        close(self, [(0, 0), (50, 0), (50, 20)], iso.trim([(0, 0), (50, 0), (50, 50)], 30))
        close(self, [(0, 0), (40, 0)], iso.trim([(0, 0), (50, 0), (50, 5)], 15))
        self.assertAlmostEqual(85, iso.path_length(iso.trim([(0, 0), (50, 0), (50, 50)], 15)))

    def test_head(self):
        tip, a, b = iso.head((100, 0), (0, 0), (14, 6))
        self.assertEqual((100, 0), tip)
        close(self, [(86, -6), (86, 6)], sorted([a, b], key=lambda p: p[1]))
        tip, a, b = iso.head((0, 50), (0, 0), (10, 5))
        self.assertAlmostEqual(40, a[1])
        self.assertAlmostEqual(a[1], b[1])
        self.assertAlmostEqual(abs(a[0] - b[0]), 10)


class DashTest(unittest.TestCase):
    def test_straight_line(self):
        pieces = iso.dashes([(0, 0), (20, 0)], 3, 3)
        self.assertEqual(4, len(pieces))
        close(self, [(0, 0), (3, 0)], pieces[0])
        close(self, [(18, 0), (20, 0)], pieces[-1])
        self.assertAlmostEqual(11, sum(iso.path_length(p) for p in pieces))

    def test_dash_runs_around_corner(self):
        pieces = iso.dashes([(0, 0), (2, 0), (2, 10)], 3, 3)
        close(self, [(0, 0), (2, 0), (2, 1)], pieces[0])
        close(self, [(2, 4), (2, 7)], pieces[1])

    def test_closed(self):
        square = [(0, 0), (10, 0), (10, 10), (0, 10)]
        total = sum(iso.path_length(p) for p in iso.dashes(square, 5, 5, closed=True))
        self.assertAlmostEqual(20, total)

    def test_edges_once(self):
        f = iso.Grid((0, 0), 40, 8).faces(0, 0)
        found = iso.edges(list(f.values()))
        self.assertEqual(9, len(found))
        self.assertEqual(len(found), len(set(found)))

    def test_rounded(self):
        pts = iso.rounded((0, 0, 100, 40), 10, steps=4)
        self.assertEqual(20, len(pts))
        x0, y0, x1, y1 = iso.box_of(pts)
        for got, want in ((x0, 0), (y0, 0), (x1, 100), (y1, 40)):
            self.assertAlmostEqual(want, got)


class TableTest(unittest.TestCase):
    def test_column_x(self):
        self.assertEqual((100, "lm"), iso.column_x(100, [80], "l"))
        self.assertEqual((180 + 60, "mm"), iso.column_x(100, [80, 120], "c"))
        self.assertEqual((300, "rm"), iso.column_x(100, [80, 120], "r"))


if __name__ == "__main__":
    unittest.main()
