"""논문의 입력·연산·출력 관계를 자체 벡터 도식과 작은 계산으로 설명함."""
from dataclasses import dataclass
import json
import math
from pathlib import Path

from PyQt6.QtCore import QPoint, QPointF, QRectF, QSize, Qt, QTimer
from PyQt6.QtGui import QFontMetricsF, QPainter, QPen, QTextLayout, QTextOption
from PyQt6.QtWidgets import QApplication, QDialog, QSizePolicy, QWidget

from gui import kit, motion, theme
from gui.dialog_layout import DialogLayout

EXPLANATIONS = Path(__file__).resolve().parents[1] / "career/data/paper_explanations.json"
PAPER_IDS = ("paper-mobilenetv4", "paper-convnext-v2", "paper-dinov2", "paper-sam2", "paper-dora-weight-decomposed")
MASK = ((0, 0, 0, 0, 0), (0, 1, 1, 1, 0), (0, 1, 1, 1, 0), (0, 0, 0, 0, 0))


def load_explanations(path=None):
    """표시할 공개 설명만 읽음. 원논문·모델·개인 기록을 내려받지 않음."""
    data = json.loads(Path(path or EXPLANATIONS).read_text(encoding="utf-8"))
    if type(data["schema_version"]) is not int or data["schema_version"] != 1 or set(data["explanations"]) != set(PAPER_IDS):
        raise ValueError("논문 그림 설명의 형식을 확인하지 못했습니다.")
    for paper in data["explanations"].values():
        if any(not isinstance(paper.get(key), str) or not paper[key].strip()
               for key in ("short_title", "axes", "idea", "boundary", "source_url")):
            raise ValueError("논문 그림의 안내를 확인하지 못했습니다.")
        if len(paper["steps"]) != 4:
            raise ValueError("논문 그림의 단계를 확인하지 못했습니다.")
        for step in paper["steps"]:
            if any(not isinstance(step[key], str) or not step[key].strip()
                   for key in ("title", "why", "text", "shape", "question", "answer")):
                raise ValueError("논문 그림의 설명을 확인하지 못했습니다.")
    return data["explanations"]


def small_examples():
    """그림에 쓰는 고정한 수치 예만 표준 연산으로 계산함."""
    first = [[row * 4 + col + 1 for col in range(4)] for row in range(4)]
    inputs = [first, [[value * 2 for value in row] for row in first]]
    depthwise = []
    for plane in inputs:
        depthwise.append([[sum(plane[rr][cc] for rr in range(max(0, row - 1), min(4, row + 2))
                               for cc in range(max(0, col - 1), min(4, col + 2)))
                           for col in range(4)] for row in range(4)])
    weights = ((1, 0), (0, 1), (1, 1), (-1, 1))
    outputs = [[[a * depthwise[0][r][c] + b * depthwise[1][r][c] for c in range(4)] for r in range(4)] for a, b in weights]
    channel_planes = (((3, 4), (0, 0)), ((6, 8), (0, 0)))
    norms = [math.sqrt(sum(value * value for row in plane for value in row)) for plane in channel_planes]
    mean = sum(norms) / len(norms)
    direction = ((3, 0), (4, 1))
    column_norms = [math.hypot(*(row[c] for row in direction)) for c in range(2)]
    unit = [[direction[r][c] / column_norms[c] for c in range(2)] for r in range(2)]
    dora = [[unit[r][c] * (5, 2)[c] for c in range(2)] for r in range(2)]
    return {"mobile": {"input": inputs, "depthwise": depthwise, "output": outputs},
            "grn": {"planes": channel_planes, "norms": norms, "mean": mean,
                    "relative": [value / mean for value in norms], "actual_relative": [value / (mean + 1e-6) for value in norms]},
            "dino": {"patches": (28 // 14) ** 2, "patch_values": 3 * 14 * 14, "tokens": 5, "width": 4},
            "sam": {"mask": MASK, "shape": (len(MASK), len(MASK[0])), "point_value": MASK[1][2]},
            "dora": {"norms": column_norms, "unit": unit, "output": dora}}


class VectorScene:
    """도형과 글자의 위치를 기록하고 같은 측정값으로 그림."""
    def __init__(self, width):
        self.width = max(1, width)
        self.operations, self.text_bounds, self.ink_groups, self.glyph_cells = [], [], [], []
        self.bottom = 0
        self.cell = max(40, theme.TYPE["body"][0] * 2 + 8)

    def text(self, text, x, y, width, role="body", color="ink", bold=False, center=False):
        layout = QTextLayout(str(text).replace("\n", "\u2028"), theme.font(role, bold))
        option = QTextOption()
        option.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        if center:
            option.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.setTextOption(option)
        layout.beginLayout()
        height = 0
        while True:
            line = layout.createLine()
            if not line.isValid():
                break
            line.setLineWidth(max(1, width))
            line.setPosition(QPointF(0, height))
            height += max(math.ceil(line.height()), theme.TYPE[role][1])
        layout.endLayout()
        ink = QRectF()
        for run in layout.glyphRuns():
            for glyph, position in zip(run.glyphIndexes(), run.positions()):
                bounds = run.rawFont().boundingRect(glyph).translated(position + QPointF(x, y))
                ink = ink.united(bounds)
        if not ink.isEmpty():
            self.ink_groups.append(ink)
        rect = QRectF(x, y, width, height)
        self.text_bounds.append(rect)
        self.operations.append(("text", layout, QPointF(x, y), color))
        self.bottom = max(self.bottom, rect.bottom())
        return height

    def glyph(self, text, rect, color="ink"):
        text, font = str(text), theme.font("body")
        metrics = QFontMetricsF(font)
        tight = metrics.tightBoundingRect(text)
        baseline = QPointF(rect.center().x() - metrics.horizontalAdvance(text) / 2,
                           rect.center().y() - (tight.top() + tight.bottom()) / 2)
        self.text_bounds.append(tight.translated(baseline))
        self.ink_groups.append(tight.translated(baseline))
        self.glyph_cells.append((QRectF(rect), tight.translated(baseline)))
        self.operations.append(("glyph", text, baseline, color))
        self.bottom = max(self.bottom, rect.bottom())

    def rect(self, rect, fill="surface_alt", edge="line", dashed=False):
        self.operations.append(("rect", rect, fill, edge, dashed))
        self.bottom = max(self.bottom, rect.bottom())

    def line(self, a, b, color="link", dashed=False, arrow=False):
        self.operations.append(("line", QPointF(*a), QPointF(*b), color, dashed, arrow))
        self.bottom = max(self.bottom, a[1], b[1])

    def circle(self, center, radius, fill="selection", edge="link"):
        self.operations.append(("circle", QPointF(*center), radius, fill, edge))
        self.bottom = max(self.bottom, center[1] + radius)

    def grid(self, x, y, values, cell=None, selected=(), tint="selection", axes=False):
        cell = cell or self.cell
        rows, cols = len(values), len(values[0])
        if axes:
            for col in range(cols):
                self.glyph(col, QRectF(x + col * cell, y - 36, cell, 32), "muted")
            for row in range(rows):
                self.glyph(row, QRectF(x - 40, y + row * cell, 32, cell), "muted")
        for row in range(rows):
            for col in range(cols):
                rect = QRectF(x + col * cell, y + row * cell, cell, cell)
                self.rect(rect, tint if (row, col) in selected else "surface_alt")
                if values[row][col] != "":
                    self.glyph(values[row][col], rect)
        return QRectF(x, y, cols * cell, rows * cell)

    def planes(self, planes, names, start=16, selected=(), axes=False, columns=2):
        grid_width = len(planes[0][0]) * self.cell
        needed = grid_width + (48 if axes else 0)
        columns = min(columns, len(planes), max(1, int((self.width - 32 + 24) // (needed + 24))))
        pane_width = (self.width - 32 - (columns - 1) * 24) / columns
        title_heights = [self.measure(name, pane_width, bold=True) for name in names]
        title_h = max(title_heights)
        rows_h = len(planes[0]) * self.cell
        pitch = title_h + 12 + (40 if axes else 0) + rows_h + 24
        rects = []
        for index, (plane, name) in enumerate(zip(planes, names)):
            left = 16 + (index % columns) * (pane_width + 24)
            top = start + (index // columns) * pitch
            self.text(name, left, top, pane_width, color="link", bold=True, center=True)
            x = left + (pane_width - needed) / 2 + (48 if axes else 0)
            y = top + title_h + 12 + (40 if axes else 0)
            rects.append(self.grid(x, y, plane, selected=selected, axes=axes))
        return rects

    def measure(self, text, width, bold=False):
        probe = VectorScene(width)
        return probe.text(text, 0, 0, width, bold=bold)

    def paint(self, painter):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        for op in self.operations:
            kind = op[0]
            if kind == "text":
                _, layout, origin, color = op
                painter.setPen(theme.qcolor(color))
                layout.draw(painter, origin)
            elif kind == "glyph":
                _, text, point, color = op
                painter.setFont(theme.font("body"))
                painter.setPen(theme.qcolor(color))
                painter.drawText(point, text)
            elif kind == "rect":
                _, rect, fill, edge, dashed = op
                painter.setBrush(theme.qcolor(fill) if fill is not None else Qt.BrushStyle.NoBrush)
                pen = QPen(theme.qcolor(edge), 2 if edge != "line" else 1)
                if dashed:
                    pen.setStyle(Qt.PenStyle.DashLine)
                painter.setPen(pen)
                painter.drawRect(rect)
            elif kind == "circle":
                _, center, radius, fill, edge = op
                painter.setPen(QPen(theme.qcolor(edge), 2))
                painter.setBrush(theme.qcolor(fill) if fill is not None else Qt.BrushStyle.NoBrush)
                painter.drawEllipse(center, radius, radius)
            elif kind == "line":
                _, a, b, color, dashed, arrow = op
                pen = QPen(theme.qcolor(color), 2)
                if dashed:
                    pen.setStyle(Qt.PenStyle.DashLine)
                painter.setPen(pen)
                painter.drawLine(a, b)
                if arrow:
                    angle = math.atan2(b.y() - a.y(), b.x() - a.x())
                    for offset in (-0.5, 0.5):
                        painter.drawLine(b, b - QPointF(9 * math.cos(angle + offset), 9 * math.sin(angle + offset)))


def _mobile(scene, stage, example):
    w = scene.width
    if stage in (0, 1, 3):
        planes = example["input"] if stage < 2 else example["output"]
        names = [f"입력 채널 {i}" for i in range(2)] if stage < 2 else [f"출력 채널 {i}" for i in range(4)]
        selected = tuple((r, c) for r in range(3) for c in range(3)) if stage == 1 else (((1, 1),) if stage == 3 else ())
        rects = scene.planes(planes, names, selected=selected)
        if stage == 1:
            for index, rect in enumerate(rects):
                border = QRectF(rect.x(), rect.y(), scene.cell * 3, scene.cell * 3)
                scene.rect(border, fill=None, edge="link", dashed=True)
                scene.line((rect.center().x(), rect.bottom() + 8), (rect.center().x(), rect.bottom() + 32), arrow=True)
                value = example["depthwise"][index][1][1]
                scene.text(f"필터 값은 모두 1 · 합 {value}", rect.x() - 24, rect.bottom() + 40, rect.width() + 48, center=True)
    else:
        left, right = 88, w - 180
        inputs = ((left, 92), (left, 252))
        targets = [(right, y) for y in (56, 156, 256, 356)]
        links = ((0,), (1,), (0, 1), (0, 1))
        for output, ins in enumerate(links):
            for source in ins:
                scene.line((inputs[source][0] + 28, inputs[source][1]), (right - 32, targets[output][1]),
                           color="muted" if output == 3 and source == 0 else "link", dashed=output == 3 and source == 0)
        for index, (x, y) in enumerate(inputs):
            scene.circle((x, y), 28)
            scene.glyph((54, 108)[index], QRectF(x - 28, y - 28, 56, 56))
            scene.text(("a", "b")[index], 16, y + 36, 144, center=True)
        for (x, y), value, label in zip(targets, (54, 108, 162, 54), ("a", "b", "a+b", "b−a")):
            scene.circle((x, y), 30)
            scene.glyph(value, QRectF(x - 30, y - 30, 60, 60))
            scene.text(label, x + 40, y - 18, w - x - 56)
        scene.text("실선은 +1, 점선은 −1을 곱하는 연결입니다.", 16, 408, w - 32, role="caption", color="muted")


def _grn(scene, stage, example):
    w = scene.width
    if stage in (0, 1):
        rects = scene.planes(example["planes"], ("채널 0 · H×W", "채널 1 · H×W"))
        if stage == 1:
            for rect, text in zip(rects, ("√(3²+4²) = 5", "√(6²+8²) = 10")):
                scene.text(text, rect.x() - 40, rect.bottom() + 24, rect.width() + 80, center=True)
    elif stage == 2:
        left, right, top = 96, w - 48, 60
        scale = (right - left) / 12
        mean_x = left + 7.5 * scale
        for index, value in enumerate(example["norms"]):
            y = top + index * 100
            scene.text(f"G{index}", 16, y, 64)
            scene.rect(QRectF(left, y, value * scale, 36), "selection", "link")
            scene.text(str(int(value)), left, y + 44, value * scale, center=True)
        scene.line((mean_x, 36), (mean_x, 236), color="retry", dashed=True)
        scene.text("채널 평균 7.5", 16, 264, w - 32, center=True)
        scene.text("5÷7.5 = 2/3       10÷7.5 = 4/3", 16, 312, w - 32, center=True)
        scene.text("그림의 손계산에서는 epsilon을 생략합니다.", 16, 368, w - 32, role="caption", color="muted", center=True)
    else:
        start_x, end_x = 56, w - 80
        scene.rect(QRectF(16, 124, 80, 64), edge="link")
        scene.glyph("X", QRectF(16, 124, 80, 64))
        middle = QRectF(w * 0.28, 28, w * 0.44, 96)
        scene.rect(middle, edge="link")
        scene.text("γ·(X·N)+β\nγ=0, β=0 → 0", middle.x() + 8, middle.y() + 12, middle.width() - 16, center=True)
        scene.line((start_x, 124), (start_x, 76))
        scene.line((start_x, 76), (middle.left(), 76), arrow=True)
        scene.line((middle.right(), 76), (end_x, 76))
        scene.line((end_x, 76), (end_x, 128), arrow=True)
        scene.line((start_x, 188), (start_x, 264), color="ok")
        scene.line((start_x, 264), (end_x, 264), color="ok")
        scene.line((end_x, 264), (end_x, 184), color="ok", arrow=True)
        scene.text("입력 X를 더하는 경로", 112, 272, w - 224, color="ok", center=True)
        scene.circle((end_x, 156), 28)
        scene.glyph("+", QRectF(end_x - 28, 128, 56, 56))
        scene.line((end_x + 28, 156), (w - 24, 156))
        scene.line((w - 24, 156), (w - 24, 332))
        scene.line((w - 24, 332), (w / 2, 332))
        scene.line((w / 2, 332), (w / 2, 344), arrow=True)
        scene.text("출력 X\n[2,2,2]", 16, 352, w - 32, bold=True, center=True)


def _patch_image(scene, x, y, size):
    half = size / 2
    for layer in (2, 1, 0):
        scene.rect(QRectF(x + layer * 8, y - layer * 8, size, size), edge="line")
    for row in range(2):
        for col in range(2):
            rect = QRectF(x + col * half, y + row * half, half, half)
            scene.rect(rect, "selection" if (row + col) % 2 == 0 else "surface_alt", "link")
            scene.glyph(row * 2 + col + 1, rect)
    scene.text("14×14", x, y + size + 12, half, center=True)
    scene.text("14×14", x + half, y + size + 12, half, center=True)


def _tokens(scene, x, y, cell, row_labels=True):
    values = [[f"{letter}{n}" for n in range(1, 5)] for letter in ("c", "f", "g", "h", "i")]
    rect = scene.grid(x, y, values, cell=cell, selected=tuple((0, c) for c in range(4)))
    if row_labels:
        for row, text in enumerate(("CLS", "패치 1", "패치 2", "패치 3", "패치 4")):
            scene.text(text, 16, y + row * cell + (cell - theme.TYPE["body"][1]) / 2, x - 28, color="link" if row == 0 else "ink")
    return rect


def _dino(scene, stage):
    w = scene.width
    if stage == 0:
        size = min(w - 96, 280)
        x = (w - size) / 2
        scene.text("RGB 3채널 · 28×28", 16, 16, w - 32, center=True)
        _patch_image(scene, x, 88, size)
    elif stage == 1:
        cell = min(80, (w - 64) / 5)
        x = (w - 5 * cell) / 2
        scene.text("패치 하나의 588개 값", 16, 16, w - 32, bold=True, center=True)
        scene.grid(x, 76, [["x1", "x2", "…", "…", "x588"]], cell=cell)
        scene.line((w / 2, 76 + cell + 8), (w / 2, 192), arrow=True)
        scene.text("같은 선형 투영 · W[588,4]", 16, 208, w - 32, center=True)
        scene.line((w / 2, 256), (w / 2, 280), arrow=True)
        out_cell = min(80, (w - 64) / 4)
        scene.grid((w - 4 * out_cell) / 2, 288, [["f1", "f2", "f3", "f4"]], cell=out_cell)
        scene.text("패치 1의 특징 · 그림용 D=4", 16, 288 + out_cell + 24, w - 32, center=True)
    elif stage == 2:
        cell = min(64, (w - 176) / 4)
        rect = _tokens(scene, 136, 64, cell)
        scene.text("특징 너비 D=4", 136, 16, 4 * cell, center=True)
        scene.text("5행 · CLS 1개와 패치 4개", 16, rect.bottom() + 24, w - 32, center=True)
        scene.text("표의 기호는 실제 계산값이 아닌 값의 자리입니다.", 16, rect.bottom() + 72, w - 32, role="caption", color="muted", center=True)
    else:
        cell = min(52, (w - 176) / 4)
        rect = _tokens(scene, 136, 16, cell)
        y = rect.bottom() + 48
        scene.line((rect.center().x(), rect.bottom() + 8), (rect.center().x(), y - 8), arrow=True)
        box = QRectF(32, y, w - 64, 96)
        scene.rect(box, edge="muted", dashed=True)
        scene.text("특징 추출기 내부\nattention 계산은 생략합니다.", 48, y + 12, w - 96, center=True)
        scene.line((w / 2, y + 104), (w / 2, y + 144), arrow=True)
        scene.text("CLS 특징 → 선택한 분류기 → 클래스 점수", 16, y + 160, w - 32, center=True)
        scene.text("특징 너비와 클래스 수를 구분합니다. 점수는 미계산입니다.", 16, y + 224, w - 32, role="caption", color="muted", center=True)


def _sam(scene, stage):
    w = scene.width
    blank = [[""] * 5 for _ in range(4)]
    selected = tuple((r, c) for r in range(4) for c in range(5) if MASK[r][c])
    if stage in (0, 1):
        rect = scene.planes([blank], ["H=4, W=5 · 왼쪽 위 [0,0]"], axes=True, columns=1)[0]
        scene.text("x →", rect.right() + 16, rect.top() - 36, 80, color="muted")
        scene.text("y ↓", rect.left() - 100, rect.center().y() - 18, 60, color="muted")
        if stage == 1:
            x, y = rect.x() + 2.5 * scene.cell, rect.y() + 1.5 * scene.cell
            scene.line((x, rect.y()), (x, y), color="retry", dashed=True)
            scene.line((rect.x(), y), (x, y), color="retry", dashed=True)
            scene.circle((x, y), 7, "retry", "retry")
            scene.text("점 [x,y]=[2,1] · 배열 [y,x]=[1,2]", 16, rect.bottom() + 24, w - 32, center=True)
        else:
            scene.text("열 x는 오른쪽, 행 y는 아래쪽으로 늘어납니다.", 16, rect.bottom() + 24, w - 32, center=True)
    elif stage == 2:
        scene.grid(32, 48, blank, cell=28)
        scene.text("이미지", 16, 184, w / 2 - 32, center=True)
        scene.circle((w - 128, 104), 28)
        scene.glyph("점", QRectF(w - 156, 76, 56, 56))
        scene.text("위치 단서 [2,1]", w / 2, 184, w / 2 - 16, center=True)
        top = 280
        scene.line((102, 224), (w / 2 - 48, top - 8), arrow=True)
        scene.line((w - 128, 224), (w / 2 + 48, top - 8), arrow=True)
        scene.rect(QRectF(32, top, w - 64, 100), edge="link")
        scene.text("SAM 2 모델\n이미지 특징 계산·내부 추론은 생략합니다.", 48, top + 12, w - 96, center=True)
        scene.line((w / 2, top + 108), (w / 2, top + 148), arrow=True)
        scene.text("대상 영역 후보 · 실제 값은 미계산", 16, top + 164, w - 32, center=True)
    else:
        rects = scene.planes([MASK, blank], ["가정 마스크", "이미지에 겹친 영역"], selected=selected, axes=True)
        for rect in rects:
            scene.circle((rect.x() + 2.5 * scene.cell, rect.y() + 1.5 * scene.cell), 18, fill=None, edge="retry")
        scene.text("원은 포함 점 [2,1]입니다. 마스크의 1은 영역을 표시합니다.", 16, max(rect.bottom() for rect in rects) + 24,
                   w - 32, role="caption", color="muted", center=True)


def _dora(scene, stage, example):
    w = scene.width
    if stage == 0:
        unit, ox, oy = min(48, (w - 144) / 6), 64, 300
        end = (ox + 3 * unit, oy - 4 * unit)
        scene.line((ox, oy), (w - 48, oy), color="muted", arrow=True)
        scene.line((ox, oy), (ox, 32), color="muted", arrow=True)
        scene.line((ox, oy), end, arrow=True)
        scene.line((end[0], oy), end, color="muted", dashed=True)
        scene.line((ox, oy), (end[0], oy), color="muted", dashed=True)
        scene.text("[3,4]", end[0] + 16, end[1] - 24, w - end[0] - 32, color="link", bold=True)
        scene.text("길이 5", ox + 32, 48, 120)
        scene.text("3", end[0] - 24, oy + 12, 48, center=True)
        scene.text("4", 16, end[1] - 16, 32)
        scene.text("[3,4]÷5 = [0.6,0.8]", 16, 376, w - 32, center=True)
    elif stage == 1:
        matrices = ([["b1"], ["b2"]], [["a1", "a2"]], [["b1a1", "b1a2"], ["b2a1", "b2a2"]])
        pane = (w - 32 - 48) / 3
        cell = min(66, (pane - 8) / 2)
        for i, (values, name) in enumerate(zip(matrices, ("B[2,1]", "A[1,2]", "BA[2,2]"))):
            left = 16 + i * (pane + 24)
            scene.text(name, left, 16, pane, center=True, color="link", bold=True)
            x = left + (pane - len(values[0]) * cell) / 2
            y = 112 + (2 - len(values)) * cell / 2
            scene.grid(x, y, values, cell=cell)
            if i < 2:
                scene.text("×" if i == 0 else "=", left + pane, 112 + cell - 18, 24, center=True)
        scene.text("안쪽 길이 1을 맞추면 바깥 길이 2와 2가 남습니다.", 16, 304, w - 32, center=True)
    elif stage == 2:
        scene.text("고정 · W0[2,2]", 16, 16, w - 32, bold=True)
        scene.rect(QRectF(32, 68, w - 64, 72), edge="muted", dashed=True)
        scene.text("기존 가중치는 바꾸지 않습니다.", 48, 84, w - 96, center=True)
        scene.text("학습 · B, A, m", 16, 180, w - 32, bold=True, color="link")
        pane = (w - 64 - 48) / 3
        for index, text in enumerate(("B[2,1]", "A[1,2]", "m[1,2]")):
            x = 32 + index * (pane + 24)
            scene.rect(QRectF(x, 232, pane, 72), edge="link")
            scene.text(text, x + 8, 248, pane - 16, center=True)
        scene.text("방향을 만들 행렬 V = W0 + BA", 16, 352, w - 32, center=True)
        scene.text("V의 열을 정규화한 뒤 크기 m을 적용합니다.", 16, 408, w - 32, role="caption", color="muted", center=True)
    else:
        unit = [[f"{value:g}" for value in row] for row in example["unit"]]
        output = [[f"{value:g}" for value in row] for row in example["output"]]
        matrices = (((3, 0), (4, 1)), unit, output)
        pane = (w - 32 - 48) / 3
        cell = min(60, (pane - 8) / 2)
        names = ("가정한 V", "열별 길이로 나눔", "크기 m을 곱함")
        titles = max(scene.measure(name, pane, bold=True) for name in names)
        for i, (values, name) in enumerate(zip(matrices, names)):
            left = 16 + i * (pane + 24)
            scene.text(name, left, 16, pane, center=True, color="link", bold=True)
            rect = scene.grid(left + (pane - 2 * cell) / 2, 16 + titles + 16, values, cell=cell)
            scene.text(("열 길이 [5,1]", "길이 1인 두 열", "m=[5,2]")[i], left, rect.bottom() + 16, pane, center=True)
            if i < 2:
                scene.line((left + pane, rect.center().y()), (left + pane + 20, rect.center().y()), arrow=True)
        scene.text("이 예의 양수 m을 곱하면 방향을 유지하고 길이가 바뀝니다.", 16, scene.bottom + 40, w - 32, center=True)


class PaperDiagram(QWidget):
    """가용 폭과 공통 글꼴을 사용해 학습용 도식을 직접 그림."""
    def __init__(self, paper_id, parent=None):
        super().__init__(parent)
        self.paper_id, self.stage = paper_id, 0
        self.examples = small_examples()
        self.last_scene = None
        policy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)
        self.setMinimumWidth(0)
        self.setAccessibleName("직접 그린 논문 학습 예시")

    def scene(self, width=None):
        scene = VectorScene(width if width is not None else self.width())
        if self.paper_id == PAPER_IDS[0]:
            _mobile(scene, self.stage, self.examples["mobile"])
        elif self.paper_id == PAPER_IDS[1]:
            _grn(scene, self.stage, self.examples["grn"])
        elif self.paper_id == PAPER_IDS[2]:
            _dino(scene, self.stage)
        elif self.paper_id == PAPER_IDS[3]:
            _sam(scene, self.stage)
        elif self.paper_id == PAPER_IDS[4]:
            _dora(scene, self.stage, self.examples["dora"])
        return scene

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return math.ceil(self.scene(width).bottom + 24)

    def minimumSizeHint(self):
        return QSize(0, 0)

    def sizeHint(self):
        return QSize(680, self.heightForWidth(680))

    def refont(self):
        self.updateGeometry()
        self.update()

    def set_stage(self, stage, description=""):
        self.stage = stage
        self.setAccessibleDescription(description)
        self.refont()

    def paintEvent(self, event):
        self.last_scene = self.scene()
        self.last_scene.paint(QPainter(self))


@dataclass
class ViewState:
    key: str = ""
    offset: int = 0
    fraction: float = 0
    relative: bool = False
    value: int = 0
    answer_open: bool = False


class PaperExplanationDialog(QDialog):
    """논문별 단계와 풀이의 펼침 상태·읽던 위치를 보관함."""
    def __init__(self, paper, parent=None):
        super().__init__(parent)
        self.paper = paper
        self.paper_id = (paper.get("paper_id", paper.get("id")) if isinstance(paper, dict)
                         else getattr(paper, "paper_id", getattr(paper, "id", None)))
        self.stage, self._restoring, self._changing = 0, False, False
        self._closing = False
        self._signature, self._passes, self.layout_stable = None, 0, True
        self._states = [ViewState() for _ in range(4)]
        self._return_focus = QApplication.focusWidget()
        try:
            self.explanation = load_explanations().get(self.paper_id)
            self.error = "이 논문의 그림 해설은 아직 제공하지 않습니다." if self.explanation is None else ""
        except (OSError, UnicodeError, ValueError, KeyError, TypeError, AttributeError):
            self.explanation = None
            self.error = "논문 그림 해설을 읽지 못했습니다. 프로그램을 업데이트한 뒤 다시 열어 주세요."
        short = self.explanation["short_title"] if self.explanation else "논문"
        self.setWindowTitle(short + " 그림 해설")
        self.panel = DialogLayout(self, short + " 그림 해설")
        self.stage_heading = kit.para("", "headline", bold=True)
        self.why = kit.para("")
        self.panel.content.addWidget(kit.heading(self.stage_heading, self.why))
        self.axes = kit.para("", "caption", "secondary")
        self.panel.content.addWidget(self.axes)
        self.prerequisite = kit.para("", "caption", "secondary")
        self.panel.content.addWidget(self.prerequisite)
        self.diagram = PaperDiagram(self.paper_id)
        self.panel.content.addWidget(self.diagram)
        self.shape = kit.para("", "body", bold=True)
        self.panel.content.addWidget(self.shape)
        self.text = kit.para("")
        self.panel.content.addWidget(self.text)
        self.question = kit.para("")
        self.panel.content.addWidget(kit.heading(kit.para("직접 확인해 보세요", "body", bold=True), self.question))
        self.answer_button = kit.button("풀이 펼치기", "text")
        self.answer_button.setCheckable(True)
        self.answer_button.toggled.connect(self._toggle_answer)
        self.panel.content.addWidget(self.answer_button, 0, Qt.AlignmentFlag.AlignLeft)
        self.answer, self.answer_layout = kit.well(pad_x=16, pad_y=16, spacing=0)
        self.answer_text = kit.para("")
        self.answer_layout.addWidget(self.answer_text)
        self.panel.content.addWidget(self.answer)
        self.answer.hide()
        self.scope = kit.para("", "caption", "secondary")
        self.panel.content.addWidget(self.scope)
        self.anchors = {"stage": self.stage_heading, "axes": self.axes, "prerequisite": self.prerequisite,
                        "diagram": self.diagram, "shape": self.shape, "text": self.text,
                        "question": self.question, "answer_button": self.answer_button, "answer": self.answer, "scope": self.scope}
        self.previous = kit.button("이전 단계")
        self.next = kit.button("다음 단계")
        self.counter = kit.label("1 / 4", "label")
        self.close_button = kit.button("닫기", "primary")
        self.previous.clicked.connect(lambda: self.set_stage(self.stage - 1))
        self.next.clicked.connect(lambda: self.set_stage(self.stage + 1))
        self.close_button.clicked.connect(self.accept)
        self.panel.actions.set_actions([self.previous, self.counter, self.next], [self.close_button])
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._restore)
        self.panel.scroll.verticalScrollBar().valueChanged.connect(self._remember)
        self.panel.scroll.verticalScrollBar().rangeChanged.connect(self._schedule_restore)
        theme.signals.changed.connect(self._theme_changed)
        if self.explanation:
            self._fill()
        else:
            self.stage_heading.setText(self.error)
            for child in (self.why, self.axes, self.prerequisite, self.diagram, self.shape, self.text,
                          self.question.parentWidget(), self.answer_button, self.scope):
                child.hide()
            self.previous.setEnabled(False)
            self.next.setEnabled(False)
            self.counter.setText("")
        self.panel.fit(760, 600)

    def _fill(self):
        self._changing = True
        row = self.explanation["steps"][self.stage]
        self.stage_heading.setText(row["title"])
        self.why.setText(row["why"])
        self.axes.setText("학습용 예시 · 모델 실행·벤치마크 결과가 아닙니다.\n" + self.explanation["axes"])
        self.prerequisite.setText(self.explanation.get("prerequisite", "") if self.stage == 0 else "")
        self.prerequisite.setVisible(bool(self.prerequisite.text()))
        self.diagram.set_stage(self.stage, row["shape"] + ". " + row["text"])
        self.shape.setText(row["shape"])
        self.text.setText(row["text"])
        self.question.setText(row["question"])
        self.answer_text.setText(row["answer"])
        self.answer_button.blockSignals(True)
        self.answer_button.setChecked(self._states[self.stage].answer_open)
        self.answer_button.setText("풀이 접기" if self._states[self.stage].answer_open else "풀이 펼치기")
        self.answer_button.blockSignals(False)
        self.answer.setVisible(self._states[self.stage].answer_open)
        self.scope.setText("직접 구성한 학습 예시이며 실제 벤치마크가 아닙니다.\n\n" + self.explanation["idea"] +
                           "\n\n" + self.explanation["boundary"] + "\n\n원논문 " + self.explanation["source_url"])
        self.counter.setText(f"{self.stage + 1} / 4")
        self.counter.setAccessibleName(f"학습 단계 {self.stage + 1} / 4")
        self.previous.setEnabled(self.stage > 0)
        self.next.setEnabled(self.stage < 3)
        self._changing = False

    def set_stage(self, stage):
        if self._closing or self.explanation is None or stage == self.stage or not 0 <= stage < 4:
            return False
        self._remember()
        self.stage = stage
        self._fill()
        self._schedule_restore()
        return True

    def _toggle_answer(self, opened):
        if self._closing:
            return
        self._remember()
        self._states[self.stage].answer_open = opened
        self.answer.setVisible(opened)
        self.answer_button.setText("풀이 접기" if opened else "풀이 펼치기")
        self._schedule_restore()

    def _remember(self, *_):
        if self._restoring or self._changing or not self.explanation:
            return
        viewport = self.panel.scroll.viewport()
        state = self._states[self.stage]
        state.value = self.panel.scroll.verticalScrollBar().value()
        options = []
        for key, widget in self.anchors.items():
            if widget.isVisibleTo(self.panel.body):
                top = widget.mapTo(viewport, QPoint()).y()
                if top + widget.height() > 0:
                    options.append((abs(top), key, top))
        if options:
            _, state.key, state.offset = min(options)
            state.relative = state.key == "diagram" and state.offset < 0
            state.fraction = -state.offset / max(1, self.diagram.height()) if state.relative else 0

    def _schedule_restore(self, *_):
        if self._closing or self._changing or not self.explanation:
            return
        self._restoring, self.layout_stable = True, False
        self._signature, self._passes = None, 0
        self._timer.start(0)

    def _restore(self):
        self._passes += 1
        bar = self.panel.scroll.verticalScrollBar()
        signature = (self.panel.body.size(), self.diagram.size(), bar.maximum(),
                     tuple(widget.pos() for widget in self.anchors.values()))
        if signature != self._signature and self._passes < 30:
            self._signature = signature
            self._timer.start(0)
            return
        self.layout_stable = self._passes < 30
        state = self._states[self.stage]
        if state.key and self.anchors[state.key].isVisibleTo(self.panel.body):
            target = self.anchors[state.key]
            offset = -state.fraction * self.diagram.height() if state.relative else state.offset
            top = target.mapTo(self.panel.scroll.viewport(), QPoint()).y()
            bar.setValue(bar.value() + round(top - offset))
        else:
            bar.setValue(state.value)
        self._restoring = False

    def refont(self):
        self._schedule_restore()

    def _theme_changed(self):
        kit.refont(self)
        self.diagram.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_timer"):
            self._schedule_restore()

    def showEvent(self, event):
        if self._return_focus is None:
            self._return_focus = QApplication.focusWidget()
        super().showEvent(event)
        self._schedule_restore()
        if not self._closing:
            effect = getattr(self, "_opacity_effect", None)
            if effect is not None:
                effect.setOpacity(0.0 if motion.enabled else 1.0)
            if motion.enabled:
                self._fade(True)

    def _fade(self, showing, done=None):
        motion.fade_opacity(self, showing, done)
        running = getattr(self, "_motion", None)
        if running is not None:
            running.valueChanged.connect(self._respect_reduced_motion)

    def _respect_reduced_motion(self, *_):
        running = getattr(self, "_motion", None)
        if running is not None and not motion.enabled and running.currentTime() < running.duration():
            running.setCurrentTime(running.duration())

    def done(self, result):
        if self._closing:
            return
        self._remember()
        self._closing, self._close_result = True, result
        self._timer.stop()
        self._restoring = False
        self.setEnabled(False)
        if motion.enabled and self.isVisible():
            self._fade(False, self._finish_close)
        else:
            motion.play(self, 0, lambda _: None, self._finish_close)

    def _finish_close(self):
        self.setEnabled(True)
        super().done(self._close_result)
        self._closing = False
        try:
            if self._return_focus is not None and self._return_focus.isVisible():
                self._return_focus.setFocus()
        except RuntimeError:
            pass
