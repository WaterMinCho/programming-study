# -*- coding: utf-8 -*-
"""해설 그림 그리기 도우미. 논리 좌표로 그리면 파일에는 SCALE 배로 찍힘. 색은 COLORS 의 토큰 이름으로 고르고,
저장할 때 모든 프레임을 PALETTE 57색으로 줄여서 같은 칸의 색이 프레임을 넘겨도 바뀌지 않음.

던전 스크립트(tools/journey_art/d01.py)는 이렇게 씀:

    from tools.journey_art.draw import figure

    @figure("1-1a", 560, 300)
    def ledger(fig):
        c = fig.frame(1400)
        rects = c.cells(20, 60, [3, 1, 4])
        c.pointer(mid_x(rects[0]), 60, "l")
        c.caption("장부 첫 줄을 품목 칸에 더합니다.")

프레임이 하나면 PNG, 둘 이상이면 GIF 로 저장됨. 색 인자는 토큰 이름("ink"), shade() 의 결과, "#rrggbb" 가운데 하나.
Pillow 가 필요하므로 출제자 컴퓨터에서만 import 함.
"""
import math
import os
import re

from PIL import Image, ImageDraw, ImageFont

from tools.journey_art import COLORS, LIMITS, NAME, SCALE

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FONT_DIR = os.path.join(ROOT, "gui", "fonts")
FONTS = {(False, False): "NanumGothic-Regular.ttf", (False, True): "NanumGothic-Bold.ttf",
         (True, False): "D2Coding-Regular.ttf", (True, True): "D2Coding-Bold.ttf"}  # (mono, bold)
CAPTION_H = 36  # 아래 설명 띠의 논리 높이
MIXES = (0.25, 0.5, 0.75)  # shade() 가 받는 섞는 비율
BRIGHT, CELL, RUN = 215, 8, 6  # 밝은 면 검사: 논리 CELL px 칸으로 줄여 밝기 BRIGHT 초과가 가로 RUN 칸 이상 이어지면 걸림
_fonts = {}


def rgb(value):
    """"#rrggbb" 를 (r, g, b) 로."""
    return tuple(int(value[i:i + 2], 16) for i in (1, 3, 5))


def shade(name, mix):
    """토큰 색을 바탕 쪽으로 mix 만큼 섞은 색. 흐리게 보일 칸·막대에 씀. 팔레트에 있는 MIXES 세 단계만 받음."""
    if mix not in MIXES:
        raise ValueError("섞는 비율은 %s 가운데 하나여야 합니다: %r" % (", ".join(str(m) for m in MIXES), mix))
    base, color = rgb(COLORS["bg"]), rgb(COLORS[name])
    return tuple(round(color[i] + (base[i] - color[i]) * mix) for i in range(3))


PALETTE = [rgb(COLORS["bg"])] + [rgb(value) for name, value in COLORS.items() if name != "bg"]
PALETTE += [shade(name, mix) for name in COLORS if name != "bg" for mix in MIXES]
PALETTE_IMAGE = Image.new("P", (1, 1))
_flat = [part for color in PALETTE for part in color]
PALETTE_IMAGE.putpalette(_flat + _flat[:3] * (256 - len(PALETTE)))  # 남는 자리는 바탕색으로 채움


def color(value):
    """색 인자를 (r, g, b) 로. None 은 그대로(채우지 않음)."""
    if value is None or isinstance(value, tuple):
        return value
    if value in COLORS:
        return rgb(COLORS[value])
    if re.match(r"^#[0-9a-fA-F]{6}$", value):
        return rgb(value)
    raise ValueError("모르는 색입니다: %r" % (value,))


def font(size, bold=False, mono=False):
    """논리 글자 크기 size 의 글꼴. 한글 설명은 나눔고딕, 숫자·코드는 mono=True 로 D2Coding."""
    key = (mono, bold, size)
    if key not in _fonts:
        path = os.path.join(FONT_DIR, FONTS[(mono, bold)])
        _fonts[key] = ImageFont.truetype(path, round(size * SCALE), layout_engine=ImageFont.Layout.BASIC)
    return _fonts[key]


def mid_x(rect):
    """(x, y, w, h) 의 가로 가운데."""
    return rect[0] + rect[2] / 2


def mid_y(rect):
    return rect[1] + rect[3] / 2


class Canvas:
    """프레임 하나. 좌표와 크기는 논리 픽셀이고 파일에는 SCALE 배로 찍힘. 그리는 메서드는 그린 자리 (x, y, w, h) 를 돌려줌."""

    def __init__(self, width, height):
        self.width, self.height = width, height
        self.im = Image.new("RGB", (width * SCALE, height * SCALE), rgb(COLORS["bg"]))
        self.d = ImageDraw.Draw(self.im)

    def _xy(self, *coords):
        return [round(v * SCALE) for v in coords]

    def _pt(self, x, y):
        return tuple(self._xy(x, y))

    def box(self, x, y, w, h, fill=None, outline="edge", width=1, radius=0):
        """사각형. fill·outline 은 색이거나 None."""
        xy = self._xy(x, y, x + w, y + h)
        if radius:
            self.d.rounded_rectangle(xy, round(radius * SCALE), fill=color(fill), outline=color(outline), width=width * SCALE)
        else:
            self.d.rectangle(xy, fill=color(fill), outline=color(outline), width=width * SCALE)
        return (x, y, w, h)

    def text(self, x, y, s, color_name="ink", size=14, bold=False, mono=False, anchor="la"):
        """글자. anchor 는 Pillow 의 기준점(la 왼쪽 위, mm 가운데, ma 가운데 위, ms 가운데 바닥, lm 왼쪽 가운데). 논리 (폭, 높이)를 돌려줌."""
        self.d.text(self._pt(x, y), s, fill=color(color_name), font=font(size, bold, mono), anchor=anchor)
        return self.text_size(s, size, bold, mono)

    def text_size(self, s, size=14, bold=False, mono=False):
        """글자의 논리 (폭, 높이)."""
        f = font(size, bold, mono)
        left, top, right, bottom = self.d.textbbox((0, 0), s, font=f)
        return f.getlength(s) / SCALE, (bottom - top) / SCALE

    def line(self, points, color_name="ink", width=1):
        """꺾은선. points 는 [(x, y), ...]."""
        self.d.line([self._pt(x, y) for x, y in points], fill=color(color_name), width=width * SCALE)

    def arrow(self, x1, y1, x2, y2, color_name="ink", width=2, head=7):
        """(x1, y1)에서 (x2, y2)로 가는 화살표. 머리는 끝점에 둠."""
        angle = math.atan2(y2 - y1, x2 - x1)
        ux, uy = math.cos(angle), math.sin(angle)
        bx, by = x2 - ux * head, y2 - uy * head
        self.line([(x1, y1), (bx, by)], color_name, width)
        side = head * 0.55
        tri = [(x2, y2), (bx - uy * side, by + ux * side), (bx + uy * side, by - ux * side)]
        self.d.polygon([self._pt(x, y) for x, y in tri], fill=color(color_name))

    def pointer(self, x, y, label, color_name="def", size=13, above=True, gap=4):
        """(x, y)를 가리키는 작은 삼각형과 그 너머의 이름(l, r, mid 같은 것). above 면 위에서 아래로 가리킴."""
        s = 1 if above else -1
        base = y - s * (gap + 8)
        tri = [(x, y - s * gap), (x - 6, base), (x + 6, base)]
        self.d.polygon([self._pt(px, py) for px, py in tri], fill=color(color_name))
        self.text(x, base - s * 2, label, color_name, size, bold=True, mono=True, anchor="ms" if above else "ma")

    def bracket(self, x1, x2, y, label=None, color_name="comment", size=13, below=True, tick=5):
        """x1..x2 를 묶는 가로 괄호와 그 바깥쪽 이름. below 면 y 에서 아래로 발을 내리고 이름을 그 밑에 둠."""
        s = 1 if below else -1
        self.line([(x1, y), (x1, y + s * tick), (x2, y + s * tick), (x2, y)], color_name, 1)
        if label:
            self.text((x1 + x2) / 2, y + s * (tick + 3), label, color_name, size, anchor="ma" if below else "ms")

    def cells(self, x, y, values, size=34, gap=4, fill="gutter", outline="edge", ink="ink", marks=None, hatch=None, index=None, text_px=None):
        """한 줄 칸과 값. marks 는 {칸 번호: 색} 으로 그 칸을 채우고, hatch 는 {칸 번호: 색} 으로 그 칸에 값 아래 빗금을 그음.
        index 가 정수면 그 번호부터 칸 아래에 작은 번호를 적음. 값이 None 이나 "" 이면 빈 칸. 칸마다 (x, y, w, h) 를 돌려줌."""
        marks, hatch = marks or {}, hatch or {}
        rects = []
        for i, value in enumerate(values):
            cx = x + i * (size + gap)
            self.box(cx, y, size, size, fill=marks.get(i, fill), outline=outline, radius=3)
            if i in hatch:
                self.hatch((cx + 1, y + 1, size - 2, size - 2), hatch[i])
            if value is not None and value != "":
                self.text(cx + size / 2, y + size / 2, str(value), ink, text_px or max(10, round(size * 0.45)), bold=True, mono=True, anchor="mm")
            if index is not None:
                self.text(cx + size / 2, y + size + 3, str(index + i), "line_no", 10, mono=True, anchor="ma")
            rects.append((cx, y, size, size))
        return rects

    def grid(self, x, y, rows, size=30, gap=2, fill="gutter", outline="edge", ink="ink", marks=None, hatch=None):
        """격자와 값. rows 는 줄마다 값 목록(None 은 빈 칸). marks 는 {(줄, 칸): 색} 으로 채우고 hatch 는 {(줄, 칸): 색} 으로
        값 아래 빗금을 그음. 줄마다 칸의 (x, y, w, h) 목록을 돌려줌."""
        marks, hatch = marks or {}, hatch or {}
        out = []
        for r, row in enumerate(rows):
            line = []
            for c, value in enumerate(row):
                cx, cy = x + c * (size + gap), y + r * (size + gap)
                self.box(cx, cy, size, size, fill=marks.get((r, c), fill), outline=outline)
                if (r, c) in hatch:
                    self.hatch((cx + 1, cy + 1, size - 2, size - 2), hatch[(r, c)])
                if value is not None and value != "":
                    self.text(cx + size / 2, cy + size / 2, str(value), ink, max(9, round(size * 0.42)), mono=True, anchor="mm")
                line.append((cx, cy, size, size))
            out.append(line)
        return out

    def bars(self, x, y, values, width=22, gap=8, height=110, vmax=None, color_name="builtin", marks=None, labels=True, ink="ink"):
        """막대그래프. y 는 바닥선이고 막대는 위로 자람. vmax 는 height 에 닿는 값(없으면 values 의 최댓값). marks 는 {번호: 색}.
        막대마다 (x, y, w, h) 를 돌려줌."""
        marks = marks or {}
        top = max(vmax if vmax is not None else max(values), 1)
        rects = []
        for i, value in enumerate(values):
            h = height * value / top
            bx = x + i * (width + gap)
            self.box(bx, y - h, width, h, fill=marks.get(i, color_name), outline=None)
            if labels:
                self.text(bx + width / 2, y - h - 3, str(value), ink, 11, mono=True, anchor="ms")
            rects.append((bx, y - h, width, h))
        self.line([(x - 4, y), (x + len(values) * (width + gap) - gap + 4, y)], "edge", 1)
        return rects

    def number_board(self, x, y, label, value, color_name="def", w=96, h=46):
        """이름과 큰 숫자가 든 숫자판("채워진 종류 2/2" 같은 것). (x, y, w, h) 를 돌려줌."""
        self.box(x, y, w, h, fill="gutter", outline="edge", radius=4)
        self.text(x + w / 2, y + 5, label, "comment", 10, anchor="ma")
        self.text(x + w / 2, y + h - 6, str(value), color_name, 18, bold=True, mono=True, anchor="ms")
        return (x, y, w, h)

    def tag(self, x, y, s, color_name="def", size=12, pad=4):
        """"+3" 같은 짧은 표시. (x, y)가 왼쪽 위인 알약 모양에 바탕색 글자. (x, y, w, h) 를 돌려줌."""
        w = self.text_size(s, size, True, True)[0] + 2 * pad
        h = size + 2 * pad
        self.box(x, y, w, h, fill=color_name, outline=None, radius=h / 2)
        self.text(x + w / 2, y + h / 2, s, "bg", size, bold=True, mono=True, anchor="mm")
        return (x, y, w, h)

    def highlight(self, rect, color_name="def", width=2, pad=2):
        """(x, y, w, h) 둘레에 테두리를 그려 강조함."""
        x, y, w, h = rect
        return self.box(x - pad, y - pad, w + 2 * pad, h + 2 * pad, fill=None, outline=color_name, width=width, radius=3)

    def hatch(self, rect, color_name="comment", step=6):
        """(x, y, w, h) 안을 빗금으로 채움. 이미 그린 것 위에 그어지므로 값이 든 칸은 cells·grid 의 hatch 인자로 그음."""
        x, y, w, h = rect
        for k in range(step, int(w + h), step):  # x + y = 일정한 사선을 상자 안에서 자름
            p1 = (x + k, y) if k <= w else (x + w, y + k - w)
            p2 = (x, y + k) if k <= h else (x + k - h, y + h)
            self.line([p1, p2], color_name, 1)
        return rect

    def caption(self, s, size=13):
        """맨 아래 CAPTION_H 띠에 이 프레임의 설명 한 줄. 바탕은 gutter."""
        self.box(0, self.height - CAPTION_H, self.width, CAPTION_H, fill="gutter", outline=None)
        self.text(12, self.height - CAPTION_H / 2, s, "ink", size, anchor="lm")


class Figure:
    """그림 하나. frame() 으로 프레임을 더하고 save() 로 씀. 프레임이 하나면 PNG, 둘 이상이면 GIF."""

    def __init__(self, name, width, height):
        if not NAME.match(name):
            raise ValueError("그림 이름은 1-1a, 1-ba 꼴이어야 합니다: %r" % (name,))
        if width > LIMITS["width"]:
            raise ValueError("논리 폭은 %dpx 이하여야 합니다: %s 가 %dpx" % (LIMITS["width"], name, width))
        self.name, self.width, self.height = name, width, height
        self.frames, self.durations = [], []

    def frame(self, ms=1400):
        """새 프레임의 캔버스. ms 는 GIF 에서 이 프레임이 보이는 시간."""
        if not LIMITS["ms_min"] <= ms <= LIMITS["ms_max"]:
            raise ValueError("프레임 시간은 %d~%dms 여야 합니다: %s 에 %dms" % (LIMITS["ms_min"], LIMITS["ms_max"], self.name, ms))
        canvas = Canvas(self.width, self.height)
        self.frames.append(canvas)
        self.durations.append(ms)
        return canvas

    @property
    def kind(self):
        return "gif" if len(self.frames) > 1 else "png"

    def images(self):
        """PALETTE 로 줄인 프레임들."""
        return [quantize(canvas.im) for canvas in self.frames]

    def save(self, folder):
        """folder/<이름>.gif 또는 .png 를 쓰고 그 경로를 돌려줌. 똑같은 프레임이 이어지면 Pillow 가 하나로 합쳐 시간을 더하므로
        프레임마다 캡션이든 표시든 무엇인가 달라야 함."""
        if not self.frames:
            raise ValueError("프레임이 없습니다: %s" % self.name)
        images = self.images()
        path = os.path.join(folder, "%s.%s" % (self.name, self.kind))
        if self.kind == "gif":
            images[0].save(path, save_all=True, append_images=images[1:], duration=self.durations, loop=0, optimize=True, disposal=1)
        else:
            images[0].save(path, optimize=True)
        return path


def quantize(image):
    """RGB 그림을 PALETTE 로 줄임(디더링 없음)."""
    return image.quantize(palette=PALETTE_IMAGE, dither=Image.Dither.NONE)


def figure(name, width, height):
    """던전 스크립트의 그림 함수 표시. 함수는 Figure 하나를 받아 프레임을 그림. render.py 가 이 표시가 붙은 함수를 모두 찾아 돌림."""
    def wrap(fn):
        fn.figure = (name, width, height)
        return fn
    return wrap


def figures(module):
    """모듈에서 @figure 가 붙은 함수를 이름 순서로 (이름, 폭, 높이, 함수) 로 냄."""
    found = [getattr(module, key) for key in dir(module)]
    found = [fn for fn in found if callable(fn) and isinstance(getattr(fn, "figure", None), tuple)]
    return sorted([fn.figure + (fn,) for fn in found], key=lambda item: item[0])


def bright_runs(image):
    """어두운 테마 화면 검사와 같은 밝은 면 검사. 회색조로 바꿔 논리 CELL px 칸으로 줄이고 밝기 BRIGHT 를 넘는 칸이
    가로로 RUN 칸 이상 이어진 곳의 수. 0 이면 통과. 글자와 가는 선은 줄어들며 바탕과 섞여 걸리지 않음."""
    step = CELL * SCALE
    small = image.convert("L").resize((max(1, image.width // step), max(1, image.height // step)), Image.Resampling.BOX)
    px, found = small.load(), 0
    for y in range(small.height):
        row = "".join("1" if px[x, y] > BRIGHT else "0" for x in range(small.width))
        found += len(re.findall("1{%d,}" % RUN, row))
    return found


def outside_palette(image):
    """그림에 PALETTE 밖의 색이 있으면 그 색들."""
    counted = image.convert("RGB").getcolors(image.width * image.height) or []
    return sorted(set(c for _, c in counted) - set(PALETTE))
