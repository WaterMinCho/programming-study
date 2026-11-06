# -*- coding: utf-8 -*-
"""단원과 전체 학습 흐름을 연결하는 그림과 짧은 되묻기를 표시함."""
import json
import math
import os

from PyQt6.QtCore import QEvent, QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QFrame, QSizePolicy, QWidget

from gui import kit, theme

ORDER = ("data", "predict", "loss", "gradient", "update")
DETAIL = {"data": "데이터·정답", "predict": "모델 출력", "loss": "오차 크기", "gradient": "손실의 변화율", "update": "파라미터"}


def unit_context(root, key):
    try:
        with open(os.path.join(root, "learning-map.json"), encoding="utf-8") as handle:
            data = json.load(handle)
        focus = data["units"][key]
        return data, focus
    except (OSError, ValueError, KeyError, TypeError):
        return None


class TrainingMap(QWidget):
    """학습의 반복과 갱신 없는 평가를 구분함. 색과 함께 굵은 테두리·현재 표시를 사용함."""

    def __init__(self, data, focus):
        super().__init__()
        self.data, self.focus = data, focus
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setAccessibleName("학습 흐름. 입력 준비, 예측, 손실, 기울기, 갱신 후 예측으로 반복. 평가는 별도 자료로 갱신 없이 수행합니다.")

    def columns(self):
        return 5 if self.width() >= 1080 else 3

    def refont(self):
        line = theme.TYPE["learn_caption"][1]
        self.setFixedHeight(math.ceil(5 / self.columns()) * (2 * line + 28) + 28)
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.refont()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        columns, gap = self.columns(), 16
        width = (self.width() - gap * (columns - 1)) / columns
        line = theme.TYPE["learn_caption"][1]
        height, boxes = 2 * line + 16, []
        for n, stage in enumerate(ORDER):
            row, column = divmod(n, columns)
            boxes.append(QRectF(column * (width + gap) + 6, row * (height + 28) + 14, width - 12, height))
        painter.setPen(QPen(theme.qcolor("border_strong"), 1.5))
        for before, after in zip(boxes, boxes[1:]):
            start, end = QPointF(before.right(), before.center().y()), QPointF(after.left(), after.center().y())
            path = QPainterPath(start)
            if after.y() > before.y():
                start = QPointF(before.center().x(), before.bottom())
                end = QPointF(after.center().x(), after.top())
                path = QPainterPath(start)
                middle = (before.bottom() + after.top()) / 2
                path.lineTo(start.x(), middle)
                path.lineTo(end.x(), middle)
                path.lineTo(end)
            else:
                path.lineTo(end)
            painter.drawPath(path)
            direction = QPointF(0, -1) if after.y() > before.y() else QPointF(-1, 0)
            side = QPointF(-direction.y(), direction.x())
            painter.drawLine(end, end + direction * 5 + side * 3)
            painter.drawLine(end, end + direction * 5 - side * 3)
        painter.setPen(QPen(theme.qcolor("primary"), 1.5, Qt.PenStyle.DashLine))
        start, end = boxes[-1], boxes[1]
        loop = QPainterPath(QPointF(start.center().x(), start.bottom()))
        loop.lineTo(start.center().x(), self.height() - 1)
        loop.lineTo(self.width() - 1, self.height() - 1)
        loop.lineTo(self.width() - 1, 2)
        loop.lineTo(end.center().x(), 2)
        loop.lineTo(end.center().x(), end.top())
        painter.drawPath(loop)
        painter.drawLine(QPointF(end.center().x(), end.top()), QPointF(end.center().x() - 3, end.top() - 5))
        painter.drawLine(QPointF(end.center().x(), end.top()), QPointF(end.center().x() + 3, end.top() - 5))
        for n, (stage, rect) in enumerate(zip(ORDER, boxes), 1):
            current = stage in self.focus
            painter.setPen(QPen(theme.qcolor("primary" if current else "border"), 2 if current else 1))
            painter.setBrush(theme.qcolor("selection" if current else "surface"))
            painter.drawRoundedRect(rect, 12, 12)
            painter.setFont(theme.font("learn_caption", current))
            painter.setPen(theme.qcolor("selection_ink" if current else "ink"))
            title = "%d. %s%s" % (n, self.data["stages"][stage]["title"], " · 현재" if current and width >= 240 else "")
            painter.drawText(rect.adjusted(8, 6, -8, -line - 8), Qt.AlignmentFlag.AlignCenter, title)
            painter.setFont(theme.font("caption"))
            painter.drawText(rect.adjusted(8, line + 8, -8, -6), Qt.AlignmentFlag.AlignCenter, DETAIL[stage])


class LearningContext(QFrame):
    reloading = pyqtSignal()

    def __init__(self, data, focus, reflect=False, expanded=True):
        super().__init__()
        self.setObjectName("learning_context")
        box = kit.box(self, (24, 24, 24, 24), 16)
        titles = [data["stages"][stage]["title"] for stage in focus]
        box.addWidget(kit.para("전체 학습에서의 위치", "learn_activity", bold=True))
        if "tools" in focus:
            box.addWidget(kit.para("파이썬·배열·텐서는 아래 학습 계산을 구현하는 도구입니다.", "learn_caption", "secondary"))
        box.addWidget(kit.para("이 단원에서 연결할 과정: %s" % " · ".join(titles), "learn_caption", "accent", bold=True))
        self.diagram = QWidget()
        diagram_box = kit.box(self.diagram, spacing=16)
        self.map = TrainingMap(data, focus)
        diagram_box.addWidget(self.map)
        diagram_box.addWidget(kit.para("점선은 다음 반복입니다. 새 배치에서 새 파라미터로 예측과 손실을 다시 계산합니다.",
                                      "learn_caption", "secondary"))
        evaluation = kit.para("별도 평가: 새 자료 → 예측 → 손실·지표 확인. 기울기 계산과 파라미터 갱신은 하지 않습니다.",
                              "learn_caption", "accent" if "evaluate" in focus else "secondary", bold="evaluate" in focus)
        diagram_box.addWidget(evaluation)
        self.flow_btn = kit.button("전체 흐름 접기" if expanded else "전체 흐름 보기", "text", "m")
        self.flow_btn.setCheckable(True)
        self.flow_btn.setChecked(expanded)
        self.diagram.setVisible(expanded)
        box.addWidget(self.flow_btn, 0, Qt.AlignmentFlag.AlignLeft)
        box.addWidget(self.diagram)
        self.flow_btn.toggled.connect(self.show_diagram)
        if reflect:
            stage = data["stages"][focus[-1]]
            box.addWidget(kit.para(stage["question"], "learn_body", bold=True))
            self.answer = kit.para(stage["answer"], "learn_body", "secondary")
            self.answer.hide()
            self.toggle = kit.button("이유 확인", "secondary", "l")
            self.toggle.setCheckable(True)
            box.addWidget(self.toggle, 0, Qt.AlignmentFlag.AlignLeft)
            box.addWidget(self.answer)
            self.toggle.toggled.connect(self.show_reason)
        self.map.refont()

    def show_reason(self, opened):
        self.reloading.emit()
        self.answer.setVisible(opened)
        self.toggle.setText("이유 접기" if opened else "이유 확인")

    def show_diagram(self, opened):
        self.reloading.emit()
        self.diagram.setVisible(opened)
        self.flow_btn.setText("전체 흐름 접기" if opened else "전체 흐름 보기")

    def event(self, event):
        result = super().event(event)
        if event.type() == QEvent.Type.LayoutRequest and hasattr(self, "map"):
            self.map.update()
        return result
