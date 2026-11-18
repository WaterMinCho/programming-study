# -*- coding: utf-8 -*-
"""입체 도식 그리기 도우미. 등각 타일, 상자, 층으로 겹친 판, 떠 있는 창과 점선 투영선, 카드, 이름표, 화살표, 표 카드를 그림.

위쪽(상수와 좌표 계산)은 표준 라이브러리만 써서 테스트가 Pillow 없이 import 함. 아래쪽 Sheet 는 만들 때 Pillow 를 import 함.
Sheet 는 파일 px 좌표(왼쪽 위가 원점, y 는 아래로)를 받아 SS 배 큰 판에 그린 뒤 BOX 로 줄임. 비스듬한 변과 곡선의 가장자리에
중간색이 생겨 계단이 보이지 않음. 저장은 지금처럼 ai_art.save 나 스크립트의 save 가 하고 quantize 가 64색으로 줄임.

    from tools.ai_art.iso import Grid, Sheet

    sheet = Sheet(1120, 460)
    grid = Grid((260, 210), cell=64)
    sheet.tiles(grid, [[1, 2, 0], [0, 3, 1], [2, 1, 4]], {(0, 0): "new", (1, 0): "new"}, default="seen")
    sheet.window(grid, 0, 0, [[1, 0], [1, 0]], lift=150)
    frame = sheet.image()

상태 이름: new = 지금 장에서 새로 나온 것(강조 면), seen = 앞 장에서 나온 것(옅은 파랑), todo = 아직 안 나온 것(회색 점선 윤곽),
normal = 강조하지 않는 것(회색 면), strong = 가장 바깥 강조(진한 파랑 면). 면 이름은 빛이 왼쪽 위에서 온다고 보고 붙임.
top 은 윗면, left 는 빛을 받는 옆면(상자는 앞면), right 는 그늘진 옆면임.
"""
from math import cos, hypot, radians, sin

from tools.ai_art import COLORS

SS = 4                 # 크게 그리는 배율. 1.5px 선이 큰 판에서 6px 로 떨어짐
MIN_SIZE = 19          # 글자 하한(파일 px). al05·al18 과 같음
LINE = 1.5             # 윤곽
DIVIDE = 1.2           # 상자·판 안 나눔선
DASH_W = 1.5           # 투영선·연결 점선
DASH = (3, 3)          # 점선 길이와 빈칸
ARROW_W = 2.5          # 화살표 줄기(2.5~3)
HEAD = (14, 6.5)       # 화살표 머리 길이와 반폭
LAYER = (16, -12)      # 뒤 장이 비끼는 간격(오른쪽 16, 위 12)
DEPTH = (0.8, -0.6)    # 상자 깊이 방향. LAYER 와 같은 방향의 단위 벡터
ANGLE = 30             # 등각 격자의 기울기(도)

INK, MUTED, WHITE = COLORS["ink"], COLORS["muted"], "#ffffff"
GRAY = "#9ca3af"
RULE = "#e5e7eb"
PANEL = "#f8fafc"

FACES = {
    "normal": {"top": "#f8fafc", "left": "#e2e8f0", "right": "#cbd5e1", "line": GRAY, "text": INK},
    "new": {"top": "#bfdbfe", "left": "#dbeafe", "right": "#93c5fd", "line": "#2563eb", "text": "#1d4ed8"},
    "seen": {"top": "#eff6ff", "left": "#dbeafe", "right": "#bfdbfe", "line": "#93c5fd", "text": INK},
    "strong": {"top": "#93c5fd", "left": "#3b82f6", "right": "#2563eb", "line": "#1d4ed8", "text": INK},
    "todo": {"top": None, "left": None, "right": None, "line": GRAY, "text": GRAY},
}
# 카드·이름표 색(옅은 칠, 테두리, 글자)
TONES = {
    "blue": ("#eff6ff", "#2563eb", "#1d4ed8"),
    "red": ("#fee2e2", "#dc2626", "#b91c1c"),
    "orange": ("#ffedd5", "#ea580c", "#c2410c"),
    "green": ("#d1fae5", "#059669", "#047857"),
    "purple": ("#ede9fe", "#7c3aed", "#6d28d9"),
    "gray": ("#f3f4f6", GRAY, MUTED),
}


def faces_of(state):
    """상태 이름의 면 색 묶음. 모르는 이름이면 ValueError."""
    if state not in FACES:
        raise ValueError("상태는 %s 가운데 하나여야 합니다: %r" % (", ".join(sorted(FACES)), state))
    return FACES[state]


def card_style(tone, state):
    """카드 한 장의 (칠, 테두리, 테두리 굵기, 글자색, 굵게, 점선). new 는 굵은 테두리와 굵은 글자, seen 은 옅은 칠과 가는
    테두리, normal 은 흰 칠과 회색 테두리, todo 는 회색 점선 윤곽. solid 는 테두리 색으로 칠하고 흰 굵은 글자를 씀.
    옅은 칠 카드 여럿 가운데 지금 단계 하나를 진하게 보일 때 씀."""
    if tone not in TONES:
        raise ValueError("색 이름은 %s 가운데 하나여야 합니다: %r" % (", ".join(sorted(TONES)), tone))
    pale, line, dark = TONES[tone]
    styles = {"new": (pale, line, 3.0, dark, True, False), "seen": (pale, line, LINE, dark, False, False),
              "normal": (WHITE, GRAY, LINE, INK, False, False), "todo": (None, GRAY, DASH_W, GRAY, False, True),
              "solid": (line, line, LINE, WHITE, True, False)}
    if state not in styles:
        raise ValueError("카드 상태는 new, seen, normal, todo, solid 가운데 하나여야 합니다: %r" % (state,))
    return styles[state]


# 좌표 계산(표준 라이브러리)

class Grid:
    """등각 격자. 원점은 (0, 0) 칸의 뒤 꼭짓점(높이 0). 열이 늘면 오른쪽 아래로, 행이 늘면 왼쪽 아래로 감.
    thick 은 타일 두께, z 는 위로 올라간 높이(px)."""

    def __init__(self, origin, cell=64, thick=14, angle=ANGLE):
        self.ox, self.oy = origin
        self.cell, self.thick = cell, thick
        self.a = cell * cos(radians(angle))
        self.b = cell * sin(radians(angle))

    def point(self, row, col, z=0.0):
        return (self.ox + (col - row) * self.a, self.oy + (col + row) * self.b - z)

    def top(self, row, col, z=None, rows=1, cols=1):
        """rows×cols 칸을 덮는 윗면 마름모 [뒤, 오른쪽, 앞, 왼쪽]. z 를 주지 않으면 타일 윗면 높이."""
        z = self.thick if z is None else z
        return [self.point(row, col, z), self.point(row, col + cols, z), self.point(row + rows, col + cols, z),
                self.point(row + rows, col, z)]

    def faces(self, row, col, lift=0.0, thick=None):
        """타일 한 칸의 {"top", "left", "right"} 다각형. 타일은 높이 lift 에서 lift + thick 까지 차지함."""
        thick = self.thick if thick is None else thick
        back, right, front, left = self.top(row, col, lift + thick)
        down = [(x, y + thick) for x, y in (left, front, right)]
        return {"top": [back, right, front, left], "left": [left, front, down[1], down[0]],
                "right": [front, right, down[2], down[1]]}

    def center(self, row, col, z=None):
        """칸 윗면 가운데."""
        return self.point(row + 0.5, col + 0.5, self.thick if z is None else z)

    def order(self, rows, cols):
        """뒤에서 앞으로 그릴 칸 순서 [(행, 열)]."""
        return sorted(((r, c) for r in range(rows) for c in range(cols)), key=lambda rc: (rc[0] + rc[1], rc[1]))

    def bounds(self, rows, cols, lift=0.0):
        """rows×cols 타일 묶음이 차지하는 (x0, y0, x1, y1)."""
        pts = self.top(0, 0, lift + self.thick, rows, cols)
        return box_of(pts + [(x, y + self.thick) for x, y in pts])


class Oblique(Grid):
    """앞뒤로 비낀 격자. 한 행의 칸은 화면에서 가로로 늘어서고, 뒤 행일수록 depth 비율만큼 오른쪽 위로 비낌. 행렬의 위·아래·
    왼쪽·오른쪽이 화면에서도 같은 쪽에 놓임. 원점은 (0, 0) 칸의 뒤 왼쪽 꼭짓점. 열이 늘면 오른쪽으로, 행이 늘면 앞(왼쪽 아래)으로
    감. 면 이름은 Grid 와 같고 left 가 앞면, right 가 오른쪽 옆면임. a·b 는 윗면 안에 넣는 글 검사에 쓰는 반폭·반높이."""

    def __init__(self, origin, cell=64, thick=14, depth=(0.5, 0.5)):
        self.ox, self.oy = origin
        self.cell, self.thick = cell, thick
        self.dx, self.dy = cell * depth[0], cell * depth[1]
        self.a, self.b = cell / 2.0, self.dy / 2.0

    def point(self, row, col, z=0.0):
        return (self.ox + col * self.cell - row * self.dx, self.oy + row * self.dy - z)

    def order(self, rows, cols):
        """뒤 행부터, 한 행 안에서는 왼쪽 칸부터. 오른쪽 옆면을 다음 칸이 덮음."""
        return [(r, c) for r in range(rows) for c in range(cols)]


def fits_diamond(width, height, a, b, room=0.9):
    """가로 width, 세로 height 인 글 상자가 반대각선 a(가로)·b(세로) 마름모 안에 room 비율로 들어가는가."""
    return width / 2.0 / a + height / 2.0 / b <= room


def box_faces(x, y, w, h, depth, direction=DEPTH):
    """앞면 왼쪽 위 (x, y), 앞면 가로 w·세로 h, 깊이 depth 인 상자의 {"left"(앞면), "top", "right"} 다각형."""
    dx, dy = direction[0] * depth, direction[1] * depth
    return {"left": [(x, y), (x + w, y), (x + w, y + h), (x, y + h)],
            "top": [(x, y), (x + w, y), (x + w + dx, y + dy), (x + dx, y + dy)],
            "right": [(x + w, y), (x + w + dx, y + dy), (x + w + dx, y + h + dy), (x + w, y + h)]}


def box_anchors(x, y, w, h, depth, direction=DEPTH):
    """상자 글자 자리. above = 윗면 위 가운데, below = 앞면 아래 가운데, center = 앞면 가운데, bbox = 상자 전체."""
    dx, dy = direction[0] * depth, direction[1] * depth
    return {"above": (x + (w + dx) / 2.0, y + min(dy, 0)), "below": (x + w / 2.0, y + h),
            "center": (x + w / 2.0, y + h / 2.0), "bbox": box_of(sum(box_faces(x, y, w, h, depth, direction).values(), []))}


def stack_offsets(n, step=LAYER):
    """판 n 장을 뒤에서 앞으로 그릴 [(앞에서 센 번호, dx, dy)]. 맨 앞 장이 (0, 0, 0)."""
    return [(k, k * step[0], k * step[1]) for k in reversed(range(n))]


def stack_anchors(x, y, w, h, n, thick, step=LAYER, direction=DEPTH):
    """판 n 장 묶음의 글 자리. above = 묶음 위 가운데, bbox = 묶음 전체, below·center = 맨 앞 장."""
    front = box_anchors(x, y, w, h, thick, direction)
    back = box_anchors(x + (n - 1) * step[0], y + (n - 1) * step[1], w, h, thick, direction)
    bbox = box_of([front["bbox"][:2], front["bbox"][2:], back["bbox"][:2], back["bbox"][2:]])
    return {"above": ((bbox[0] + bbox[2]) / 2.0, bbox[1]), "below": front["below"], "center": front["center"],
            "bbox": bbox}


def window_lines(grid, row, col, rows, cols, lift):
    """타일 위로 lift 만큼 띄운 rows×cols 창의 바깥 꼭짓점 넷에서 타일 윗면 꼭짓점까지 내리는 선 [(위, 아래)]."""
    top = grid.top(row, col, grid.thick + lift, rows, cols)
    low = grid.top(row, col, grid.thick, rows, cols)
    return list(zip(top, low))


def bezier(start, end, bend=0.0, steps=32):
    """start 에서 end 로 가는 2차 곡선 점 목록. bend 는 줄 길이에 곱한 휨 정도이고 양수면 진행 방향의 왼쪽(화면 기준)으로 휨."""
    (x0, y0), (x1, y1) = start, end
    length = hypot(x1 - x0, y1 - y0)
    if not bend or not length:
        return [start, end]
    nx, ny = (y1 - y0) / length, -(x1 - x0) / length
    cx, cy = (x0 + x1) / 2.0 + nx * bend * length, (y0 + y1) / 2.0 + ny * bend * length
    pts = []
    for k in range(steps + 1):
        t = k / float(steps)
        u = 1 - t
        pts.append((u * u * x0 + 2 * u * t * cx + t * t * x1, u * u * y0 + 2 * u * t * cy + t * t * y1))
    return pts


def path_length(points):
    return sum(hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(points, points[1:]))


def trim(points, length):
    """꺾은선 끝에서 length 만큼 잘라낸 점 목록. 화살표 줄기가 머리 끝을 넘지 않게 씀."""
    pts = list(points)
    while len(pts) > 1 and length > 0:
        (ax, ay), (bx, by) = pts[-2], pts[-1]
        seg = hypot(bx - ax, by - ay)
        if seg > length:
            k = (seg - length) / seg
            pts[-1] = (ax + (bx - ax) * k, ay + (by - ay) * k)
            return pts
        length -= seg
        pts.pop()
    return pts


def head(tip, toward, size=HEAD):
    """끝점 tip, 직전 점 toward 인 화살표 머리 삼각형 [끝, 왼쪽, 오른쪽]."""
    length, half = size
    dx, dy = tip[0] - toward[0], tip[1] - toward[1]
    norm = hypot(dx, dy) or 1.0
    dx, dy = dx / norm, dy / norm
    bx, by = tip[0] - dx * length, tip[1] - dy * length
    return [tip, (bx + dy * half, by - dx * half), (bx - dy * half, by + dx * half)]


def dashes(points, on=DASH[0], off=DASH[1], closed=False):
    """꺾은선을 on 만큼 긋고 off 만큼 비운 조각 목록 [[점, …]]."""
    pts = list(points) + ([points[0]] if closed else [])
    out, cur, drawing, left = [], [pts[0]], True, on
    for a, b in zip(pts, pts[1:]):
        seg = hypot(b[0] - a[0], b[1] - a[1])
        pos = 0.0
        while seg - pos > left:
            pos += left
            k = pos / seg
            p = (a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k)
            if drawing:
                cur.append(p)
                out.append(cur)
            else:
                cur = [p]
            drawing, left = not drawing, (off if drawing else on)
        left -= seg - pos
        if drawing:
            cur.append(b)
    if drawing and len(cur) > 1:
        out.append(cur)
    return out


def edges(polygons):
    """다각형 목록의 변을 한 번씩만 [(점, 점)]. 이웃한 면이 같이 쓰는 변을 점선으로 두 번 긋지 않게 씀."""
    seen, out = set(), []
    for poly in polygons:
        for a, b in zip(poly, poly[1:] + poly[:1]):
            a, b = (round(a[0], 3), round(a[1], 3)), (round(b[0], 3), round(b[1], 3))
            key = (a, b) if a <= b else (b, a)
            if key not in seen:
                seen.add(key)
                out.append(key)
    return out


def rounded(rect, radius, steps=6):
    """둥근 사각형 윤곽 점 목록(시계 방향). 점선 윤곽을 그릴 때 씀."""
    x0, y0, x1, y1 = rect
    r = min(radius, (x1 - x0) / 2.0, (y1 - y0) / 2.0)
    pts = []
    for cx, cy, start in ((x1 - r, y0 + r, -90), (x1 - r, y1 - r, 0), (x0 + r, y1 - r, 90), (x0 + r, y0 + r, 180)):
        for k in range(steps + 1):
            t = radians(start + 90.0 * k / steps)
            pts.append((cx + r * cos(t), cy + r * sin(t)))
    return pts


def box_of(points):
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    return (min(xs), min(ys), max(xs), max(ys))


def column_x(x, widths, align):
    """표 한 칸의 글 기준 x 와 Pillow anchor. align 은 l·c·r."""
    left = x + sum(widths[:-1])
    return {"l": (left, "lm"), "c": (left + widths[-1] / 2.0, "mm"), "r": (left + widths[-1], "rm")}[align]


# 그리기(출제자 컴퓨터에서만)

class Sheet:
    """파일 px 좌표로 받아 SS 배 판에 그리는 그림 한 장. image() 가 줄인 RGB 그림을 돌려줌."""

    def __init__(self, width, height, ss=SS, background=WHITE):
        from PIL import Image, ImageDraw
        self.width, self.height, self.ss = width, height, ss
        self.big = Image.new("RGB", (width * ss, height * ss), background)
        self.d = ImageDraw.Draw(self.big)

    def image(self):
        from PIL import Image
        return self.big.resize((self.width, self.height), Image.Resampling.BOX)

    # 바탕 도구

    def _p(self, points):
        return [(x * self.ss, y * self.ss) for x, y in points]

    def _px(self, width):
        return max(1, int(round(width * self.ss)))

    def _face(self, size, bold, code):
        from tools.ai_art.al18 import _face
        return _face(int(round(size * self.ss)), bold, code)

    def measure(self, value, size=21, bold=False, code=False):
        """글 한 줄의 폭(파일 px)."""
        return self._face(size, bold, code).getlength(str(value)) / self.ss

    def poly(self, points, fill=None, line=None, width=LINE):
        if fill:
            self.d.polygon(self._p(points), fill=fill)
        if line:
            pts = self._p(points)
            self.d.line(pts + pts[:2], fill=line, width=self._px(width), joint="curve")

    def path(self, points, color, width=LINE, dash=None, closed=False):
        """꺾은선. dash=(긋기, 비우기) 면 점선."""
        if dash:
            for piece in dashes(points, dash[0], dash[1], closed):
                self.d.line(self._p(piece), fill=color, width=self._px(width), joint="curve")
            return
        pts = self._p(points)
        if closed:
            pts = pts + pts[:2]
        self.d.line(pts, fill=color, width=self._px(width), joint="curve")

    def text(self, xy, value, size=21, color=INK, bold=False, code=False, anchor="la"):
        """글자 한 줄. 그림 밖으로 나가거나 하한보다 작으면 assert 로 멈춤. 나눔고딕에 없는 U+2212 는 코드 글꼴로만 씀.
        차지한 상자(파일 px)를 돌려줌."""
        value = str(value)
        assert size >= MIN_SIZE, (value, size)
        assert code or "−" not in value, value
        face = self._face(size, bold, code)
        at = (xy[0] * self.ss, xy[1] * self.ss)
        box = [v / float(self.ss) for v in self.d.textbbox(at, value, font=face, anchor=anchor)]
        assert box[0] >= 8 and box[1] >= 6 and box[2] <= self.width - 8 and box[3] <= self.height - 6, (value, box)
        self.d.text(at, value, font=face, fill=color, anchor=anchor)
        return tuple(box)

    def prose(self, xy, value, size=21, color=INK, bold=False):
        """왼쪽 가운데가 xy 인 글 한 줄. 나눔고딕으로 쓰고 나눔고딕에 없는 U+2212 만 DejaVu Sans 로 바꿔 같은 기준선에 씀.
        matplotlib 그림이 빼기표를 DejaVu Sans 로 대신 그리던 것과 같은 모양이 됨. 끝난 x 를 돌려줌."""
        import os
        import matplotlib
        from PIL import ImageFont
        ascent, descent = self._face(size, bold, False).getmetrics()
        base = xy[1] + (ascent - descent) / 2.0 / self.ss
        minus = ImageFont.truetype(os.path.join(matplotlib.get_data_path(), "fonts", "ttf",
                                                "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"),
                                   int(round(size * self.ss)))
        x = xy[0]
        for k, part in enumerate(str(value).split("−")):
            if k:
                at = (x * self.ss, base * self.ss)
                box = [v / float(self.ss) for v in self.d.textbbox(at, "−", font=minus, anchor="ls")]
                assert box[0] >= 8 and box[2] <= self.width - 8, (value, box)
                self.d.text(at, "−", font=minus, fill=color, anchor="ls")
                x += minus.getlength("−") / self.ss
            if part:
                self.text((x, base), part, size, color, bold, False, anchor="ls")
                x += self.measure(part, size, bold, False)
        return x

    def _solid(self, polys, state):
        """면 다각형 {"top", "left", "right"} 을 상태 색으로 칠하고 윤곽을 그림. todo 는 회색 점선 윤곽만.
        그림 밖으로 나가면 assert 로 멈춤."""
        style = faces_of(state)
        x0, y0, x1, y1 = box_of(sum(polys.values(), []))
        assert x0 >= 2 and y0 >= 2 and x1 <= self.width - 2 and y1 <= self.height - 2, (state, (x0, y0, x1, y1))
        if state == "todo":
            for a, b in edges(list(polys.values())):
                self.path([a, b], style["line"], DASH_W, DASH)
            return
        for name in ("top", "left", "right"):
            if name in polys:
                self.poly(polys[name], fill=style[name])
        for name in ("top", "left", "right"):
            if name in polys:
                self.poly(polys[name], line=style["line"], width=LINE)

    # 입체 부품

    def tile(self, grid, row, col, state="normal", value=None, lift=0.0, thick=None, size=22, code=True, bold=True):
        """등각 타일 한 칸. value 는 윗면 가운데 글이고 마름모를 넘으면 assert. 윗면 가운데 점을 돌려줌."""
        thick = grid.thick if thick is None else thick
        self._solid(grid.faces(row, col, lift, thick), state)
        center = grid.center(row, col, lift + thick)
        if value is not None and value != "":
            value = str(value)
            assert fits_diamond(self.measure(value, size, bold, code), size, grid.a, grid.b), (value, size)
            self.text(center, value, size, faces_of(state)["text"], bold, code, anchor="mm")
        return center

    def tiles(self, grid, values, states=None, default="normal", lift=0.0, size=22):
        """values(행 목록) 칸을 뒤에서 앞으로 그림. states 는 {(행, 열): 상태} 나 함수(행, 열) → 상태. 값이 None 이면 글 없음.
        todo 칸은 점선 윤곽만이라 먼저 그림. 이웃한 칠한 칸의 면과 윤곽 위로 점선이 지나가지 않음."""
        rows, cols = len(values), len(values[0])
        cells = [(r, c, states(r, c) if callable(states) else (states or {}).get((r, c), default))
                 for r, c in grid.order(rows, cols)]
        for r, c, state in sorted(cells, key=lambda cell: cell[2] != "todo"):
            self.tile(grid, r, c, state, values[r][c], lift, size=size)

    def window(self, grid, row, col, values, states=None, default="new", lift=150.0, thick=5, size=22,
               corners=(0, 1, 3)):
        """(row, col) 부터 타일 위로 lift 만큼 띄운 창. 바깥 꼭짓점에서 아래 칸 꼭짓점으로 점선 투영선을 먼저 그리고
        창 칸을 그 위에 그림. states 로 창 안 일부 칸만 강조함. corners 는 투영선을 내릴 꼭짓점 번호(0 뒤, 1 오른쪽,
        2 앞, 3 왼쪽)이고, 앞 꼭짓점 선은 아래 칸 숫자를 가로지르기 쉬워 기본에서 뺐음."""
        rows, cols = len(values), len(values[0])
        line = faces_of(default)["line"]
        lines = window_lines(grid, row, col, rows, cols, lift)
        for k in corners:
            self.path(list(lines[k]), line, DASH_W, DASH)
        for r, c in grid.order(rows, cols):
            state = states(r, c) if callable(states) else (states or {}).get((r, c), default)
            self.tile(grid, row + r, col + c, state, values[r][c], lift + grid.thick - thick, thick, size)
        return box_of(grid.top(row, col, grid.thick + lift, rows, cols))

    def box(self, x, y, w, h, depth, state="normal", value=None, size=22, code=True, bold=True):
        """앞면 왼쪽 위 (x, y), 앞면 가로 w·세로 h, 깊이 depth 인 상자. 글 자리 {"above", "below", "center", "bbox"} 를 돌려줌."""
        self._solid(box_faces(x, y, w, h, depth), state)
        anchors = box_anchors(x, y, w, h, depth)
        if value is not None and value != "":
            assert self.measure(value, size, bold, code) <= w - 8 and size <= h - 4, (value, w, h)
            self.text(anchors["center"], value, size, faces_of(state)["text"], bold, code, anchor="mm")
        return anchors

    def stack(self, x, y, w, h, n, rows=1, cols=1, thick=6, states=None, default="new", step=LAYER):
        """판 n 장을 겹침. 맨 앞 장 앞면이 (x, y, w, h) 이고 뒤 장일수록 step 만큼 오른쪽 위로 비낌. 판마다 앞면을
        rows×cols 로 나눔. states 는 앞에서 센 번호 → 상태(목록이나 dict). 글 자리를 돌려줌. above·bbox 는 판 전체,
        below·center 는 맨 앞 장 기준."""
        anchors = stack_anchors(x, y, w, h, n, thick, step)
        for k, dx, dy in stack_offsets(n, step):
            if isinstance(states, (list, tuple)):
                state = states[k]
            else:
                state = (states or {}).get(k, default)
            self.box(x + dx, y + dy, w, h, thick, state)
            if state != "todo":
                line = faces_of(state)["line"]
                for i in range(1, cols):
                    gx = x + dx + w * i / float(cols)
                    self.path([(gx, y + dy), (gx, y + dy + h)], line, DIVIDE)
                for j in range(1, rows):
                    gy = y + dy + h * j / float(rows)
                    self.path([(x + dx, gy), (x + dx + w, gy)], line, DIVIDE)
        return anchors

    def slab(self, x, y, cw, ch, rows, cols, depth, state="new", values=None, size=24, code=True, bold=True):
        """칸 rows×cols 개를 붙여 놓은 상자. 앞면 왼쪽 위가 (x, y), 칸 하나는 가로 cw·세로 ch. 앞면을 칸으로 나누고 윗면에는
        열 나눔선, 옆면에는 행 나눔선을 그어 작은 상자를 붙인 모양이 됨. values(행 목록)는 앞면 칸 가운데 글이고 칸을 넘으면
        assert. 글 자리를 돌려줌."""
        w, h = cw * cols, ch * rows
        self._solid(box_faces(x, y, w, h, depth), state)
        anchors = box_anchors(x, y, w, h, depth)
        if state == "todo":
            return anchors
        style = faces_of(state)
        dx, dy = DEPTH[0] * depth, DEPTH[1] * depth
        for i in range(1, cols):
            gx = x + cw * i
            self.path([(gx, y + h), (gx, y), (gx + dx, y + dy)], style["line"], DIVIDE)
        for j in range(1, rows):
            gy = y + ch * j
            self.path([(x, gy), (x + w, gy), (x + w + dx, gy + dy)], style["line"], DIVIDE)
        for j, row in enumerate(values or []):
            for i, value in enumerate(row):
                if value is None or value == "":
                    continue
                assert self.measure(value, size, bold, code) <= cw - 8 and size <= ch - 4, (value, cw, ch)
                self.text((x + cw * (i + 0.5), y + ch * (j + 0.5)), value, size, style["text"], bold, code, anchor="mm")
        return anchors

    # 평면 부품

    def card(self, center, lines, tone="blue", state="new", size=21, pad=(20, 12), width=None, radius=10, gap=8,
             code=False):
        """둥근 카드 가운데에 여러 줄. lines 항목은 글이나 (글, 색, 굵게, 코드글꼴). 폭은 width 나 가장 긴 줄 + 여백.
        카드 상자(파일 px)를 돌려줌."""
        fill, line, line_w, ink, heavy, dashed = card_style(tone, state)
        rows = [item if isinstance(item, tuple) else (item, ink, heavy, code) for item in lines]
        need = max(self.measure(v, size, b, m) for v, _, b, m in rows) + 2 * pad[0]
        width = width or need
        assert need <= width + 0.5, (lines, width)
        height = len(rows) * size + (len(rows) - 1) * gap + 2 * pad[1] + 4
        rect = (center[0] - width / 2.0, center[1] - height / 2.0, center[0] + width / 2.0, center[1] + height / 2.0)
        if dashed:
            self.path(rounded(rect, radius), line, line_w, DASH, closed=True)
        else:
            self.d.rounded_rectangle(self._p([rect[:2], rect[2:]]), radius * self.ss, fill=fill, outline=line,
                                     width=self._px(line_w))
        y = center[1] - (height - 2 * pad[1] - 4) / 2.0 + size / 2.0
        for value, color, bold, mono in rows:
            self.text((center[0], y), value, size, color, bold, mono, anchor="mm")
            y += size + gap
        return rect

    def plate(self, rect, fill=PANEL, line=RULE, radius=12, width=LINE):
        """둥근 사각형 판 (x0, y0, x1, y1). line 이 None 이면 테두리 없이 칠만 함. 강조 띠는 옅은 칠에 테두리 없이 씀."""
        x0, y0, x1, y1 = rect
        assert x0 >= 2 and y0 >= 2 and x1 <= self.width - 2 and y1 <= self.height - 2, rect
        self.d.rounded_rectangle(self._p([rect[:2], rect[2:]]), radius * self.ss, fill=fill, outline=line,
                                 width=self._px(width) if line else 0)
        return rect

    def label(self, center, value, tone="purple", state="seen", size=19, code=False, width=None):
        """한 줄 이름표. 계산식 띠는 tone="blue", code=True 로 씀."""
        return self.card(center, [value], tone, state, size, (12, 5), width, 8, code=code)

    def arrow(self, start, end, color=GRAY, bend=0.0, width=ARROW_W, dash=None, size=HEAD):
        """곧은 화살표(bend=0)나 곡선 화살표. 머리는 end 에 붙고 줄기는 머리 안쪽에서 끝남."""
        pts = bezier(start, end, bend)
        self.path(trim(pts, size[0] * 0.7), color, width, dash)
        self.d.polygon(self._p(head(end, trim(pts, size[0])[-1], size)), fill=color)

    def table(self, x, y, widths, header, rows, aligns=None, size=21, row_h=46, band=None, pad=20, code=True):
        """표 카드. header·rows 의 칸은 글이나 (글, 색, 굵게, 코드글꼴). 머리 줄은 회색 보통 글, 줄 사이 가는 선.
        band=(글, 색 이름) 이면 아래에 옅은 칠 띠. 카드 상자를 돌려줌."""
        aligns = aligns or "l" * len(widths)
        inner = sum(widths)
        top = y + pad
        height = pad * 2 + row_h * (1 + len(rows)) + (row_h + 16 if band else 0)
        rect = (x, y, x + inner + 2 * pad, y + height)
        self.d.rounded_rectangle(self._p([rect[:2], rect[2:]]), 12 * self.ss, fill=PANEL, outline=RULE,
                                 width=self._px(LINE))
        for n, row in enumerate([header] + list(rows)):
            cy = top + row_h * n + row_h / 2.0
            for k, cell in enumerate(row):
                value, color, bold, mono = cell if isinstance(cell, tuple) else (
                    (cell, MUTED, False, False) if n == 0 else (cell, INK, True, code))
                at, anchor = column_x(x + pad, widths[:k + 1], aligns[k])
                assert self.measure(value, size, bold, mono) <= widths[k] - 4, (value, widths[k])
                self.text((at, cy), value, size, color, bold, mono, anchor)
            line_y = top + row_h * (n + 1)
            if n < len(rows):
                self.path([(x + pad, line_y), (x + pad + inner, line_y)], RULE, DIVIDE)
        if band:
            value, tone = band
            pale, line, dark = TONES[tone]
            by = top + row_h * (1 + len(rows)) + 16
            self.d.rounded_rectangle(self._p([(x + pad, by), (x + pad + inner, by + row_h)]), 8 * self.ss, fill=pale,
                                     outline=None)
            self.text((x + pad + inner / 2.0, by + row_h / 2.0), value, size, line, True, code, anchor="mm")
        return rect
