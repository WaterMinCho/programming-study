"""추천 주제의 입력·변화 예시를 원래 순서대로 연결함. 학습 기록을 읽거나 쓰지 않음."""
import math

from PyQt6.QtCore import QPointF, QRect, QRectF, QSize, Qt
from PyQt6.QtGui import QFontMetricsF, QPainter, QPen, QPolygonF
from PyQt6.QtWidgets import QSizePolicy, QWidget

from career.catalog import COURSE_LABELS
from gui import kit, theme


# 설명용 입력과 변화를 적음. 수업 범위와 개인의 학습 진도를 연결하지 않음.
EXAMPLES = {
    "C++ 실전": ("pipeline", "왼쪽부터 입력 읽기·제어 값 계산·장치 쓰기 순서입니다."),
    "좌표계와 변환": ("axes", "왼쪽은 센서 좌표이고 오른쪽은 로봇 좌표입니다. 같은 점의 위치를 두 좌표로 나타냅니다."),
    "좌표 변환": ("axes", "센서에서 읽은 같은 점을 왼쪽 센서 좌표와 오른쪽 로봇 좌표로 나타냅니다."),
    "ROS2 기본": ("nodes", "센서 노드가 보낸 값을 처리 노드에서 받아 다음 노드에 전합니다."),
    "통신과 실시간성": ("messages", "가로축은 시간입니다. 1·2번의 송신·수신 시각을 화살표로 잇고 3번의 수신 기록이 없는 자리를 ×로 표시합니다."),
    "ros2_control": ("response", "가로축은 시간, 세로축은 위치입니다. 회색 점선은 목표 위치이고 파란 실선은 장치 응답입니다."),
    "센서 데이터": ("signal", "가로축은 시간, 세로축은 센서 값입니다. 파란 선의 솟은 구간에서 튀는 값을 확인합니다."),
    "2D SLAM": ("map", "격자 지도에 벽과 로봇이 지나온 경로를 함께 표시합니다."),
    "Nav2": ("route", "지도에 출발점과 목적지를 놓고 장애물을 피하는 경로를 만듭니다."),
    "주행 실패 복구": ("recovery", "회색 점선은 장애물에 막힌 이전 경로입니다. 파란 실선은 다시 계획한 우회 경로입니다."),
    "데이터 다루기": ("table", "왼쪽 자료 표에서 파란 행을 고르고 오른쪽에 일부 항목을 옮깁니다."),
    "PyTorch 기본": ("matrix", "입력 배열을 모델에 넣고 출력 배열의 모양을 확인합니다."),
    "PyTorch": ("matrix", "입력 배열을 모델에 넣고 출력 배열의 모양을 확인합니다."),
    "이미지 분류 모델": ("image", "영상의 모양을 입력으로 받아 어느 종류인지 예측합니다."),
    "학습 튜닝": ("curve", "가로축은 학습 반복, 세로축은 손실입니다. 파란 실선은 학습 손실이고 회색 점선은 검증 손실입니다."),
    "Linux 운영": ("process", "가로축은 시간입니다. 파란 막대는 프로세스의 실행 구간이며 ×는 멈춘 시점을 나타냅니다."),
    "네트워크 기초": ("nodes", "장치에서 서버까지 이어진 연결을 따라 도달 여부를 확인합니다."),
    "장애 대응": ("compare", "오류가 난 조건을 다시 만들고 조치 전후의 기록을 비교합니다."),
    "기술문서 작성": ("table", "작업 조건과 기대 결과를 표의 같은 행에 적어 재현 순서를 남깁니다."),
    "ROS2와 로봇 모델": ("robot", "URDF로 몸체의 링크와 링크 사이 관절을 연결합니다. 메시지를 주고받는 ROS 실행 노드와 구분합니다."),
    "시뮬레이터": ("route", "가상 환경의 로봇과 장애물을 배치하고 움직임을 관찰합니다."),
    "강화학습 기초": ("reward", "가로축은 반복이고 세로축은 환경에서 얻은 보상입니다. 보상은 반복마다 오르내릴 수 있습니다."),
    "모방학습": ("compare", "시범 동작과 같은 입력에서 정책이 고른 동작을 비교합니다."),
    "VLA 모델": ("matrix", "영상과 언어 지시를 입력으로 연결해 로봇 동작 출력을 살펴봅니다."),
    "로봇 정책 평가": ("compare", "같은 환경에서 정책별 결과를 모으고 실패 조건을 비교합니다."),
    "SQL과 DB": ("table", "행과 열로 저장한 자료에서 조건에 맞는 행을 골라 냅니다."),
    "백엔드 API": ("request", "실선 화살표는 요청 처리 순서이고 아래쪽 점선 화살표는 응답이 돌아오는 방향입니다."),
    "실시간 통신": ("messages", "가로축은 시간입니다. 1·2번의 송신·수신 시각 차이가 지연입니다. 3번은 관측 구간에 수신 기록이 없는 예시입니다."),
    "ROS2 연동": ("nodes", "ROS2 노드의 메시지를 받아 서버가 쓰는 값으로 연결합니다."),
    "컨테이너": ("deploy", "프로그램과 실행 환경을 묶어 같은 구성으로 실행합니다."),
    "배포와 운영": ("deploy", "배포할 버전과 이전 버전을 나란히 두고 되돌릴 순서를 정합니다."),
    "HTTP와 웹 기초": ("request", "요청 처리 순서를 실선 화살표로 잇고 응답이 돌아오는 방향을 아래쪽 점선 화살표로 표시합니다."),
    "JavaScript": ("interaction", "입력 이벤트를 받아 상태를 바꾸고 화면에 반영하는 순서를 잇습니다."),
    "TypeScript": ("table", "입력 값의 항목과 자료형을 적고 맞지 않는 연결을 찾습니다."),
    "React": ("screen", "입력에 따라 상태가 바뀌면 화면의 해당 부분을 다시 표시합니다."),
    "화면 품질": ("screen", "같은 내용을 넓고 좁은 화면에 놓고 입력과 오류가 보이는지 확인합니다."),
    "테스트 설계": ("table", "입력 조건과 기대 결과를 짝지어 정상·경계·오류 사례를 만듭니다."),
}


def _sizing(widget):
    policy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    policy.setHeightForWidth(True)
    widget.setSizePolicy(policy)


class _Example(QWidget):
    """카드의 설명과 함께 읽는 합성 도식임. 실제 측정값을 표시하지 않음."""
    def __init__(self, kind, description, parent):
        super().__init__(parent)
        self.kind = kind
        self.setAccessibleName("학습 주제의 입력과 변화 예시")
        self.setAccessibleDescription(description)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        area = QRectF(self.rect()).adjusted(8, 8, -8, -8)
        self.label_bounds = []

        def point(x, y):
            return QPointF(area.left() + area.width() * x / 100, area.top() + area.height() * y / 100)

        def line(points, tone="link", dashed=False):
            pen = QPen(theme.qcolor(tone), 2)
            if dashed:
                pen.setStyle(Qt.PenStyle.DashLine)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPolyline(QPolygonF([point(x, y) for x, y in points]))

        def arrow(points, tone="link", dashed=False):
            line(points, tone, dashed)
            start, end = point(*points[-2]), point(*points[-1])
            delta = end - start
            length = math.hypot(delta.x(), delta.y())
            if not length:
                return
            along = delta / length
            across = QPointF(-along.y(), along.x())
            # 화살촉은 창 폭과 무관한 화면 단위로 그림.
            p.setPen(QPen(theme.qcolor(tone), 2))
            p.drawPolyline(QPolygonF([end - along * 6 + across * 4, end, end - along * 6 - across * 4]))

        def box(x, y, w, h, tone="surface", edge="border"):
            p.setBrush(theme.qcolor(tone))
            p.setPen(QPen(theme.qcolor(edge), 1.5))
            p.drawRoundedRect(QRectF(point(x, y), point(x + w, y + h)), 4, 4)

        def dot(x, y):
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(theme.qcolor("link"))
            p.drawEllipse(point(x, y), 4, 4)

        def cross(x, y):
            center = point(x, y)
            p.setPen(QPen(theme.qcolor("wrong"), 2))
            p.drawLine(center + QPointF(-5, -5), center + QPointF(5, 5))
            p.drawLine(center + QPointF(-5, 5), center + QPointF(5, -5))

        def label(x, y, text):
            p.setFont(theme.font("caption"))
            p.setPen(theme.qcolor("muted"))
            metrics = QFontMetricsF(p.font())
            bounds = metrics.tightBoundingRect(text)
            origin = point(x, y) - bounds.center()
            ink = bounds.translated(origin)
            room = QRectF(self.rect()).adjusted(1, 1, -1, -1)
            shift = QPointF(max(room.left() - ink.left(), 0) + min(room.right() - ink.right(), 0),
                            max(room.top() - ink.top(), 0) + min(room.bottom() - ink.bottom(), 0))
            origin += shift
            self.label_bounds.append((text, bounds.translated(origin)))
            p.drawText(origin, text)

        if self.kind == "axes":
            line([(8, 15), (8, 85), (42, 85)], "muted")
            line([(62, 15), (62, 85), (96, 85)], "muted")
            dot(26, 35)
            dot(84, 60)
            arrow([(30, 35), (48, 35), (48, 60), (78, 60)])
        elif self.kind == "matrix":
            for x, cols in ((4, 3), (68, 2)):
                for row in range(2):
                    for col in range(cols):
                        box(x + col * 12, 22 + row * 27, 10, 23, "selection", "link")
            arrow([(45, 48), (61, 48)])
        elif self.kind == "nodes":
            for x, y in ((2, 38), (39, 12), (76, 38)):
                box(x, y, 22, 35, "selection", "link")
            arrow([(24, 55), (31, 55), (31, 30), (39, 30)])
            arrow([(61, 30), (68, 30), (68, 55), (76, 55)])
        elif self.kind == "messages":
            for y, name in ((24, "송신"), (66, "수신")):
                label(11, y, name)
                line([(24, y), (96, y)], "muted")
            for number, sent in enumerate((30, 55, 78), 1):
                dot(sent, 24)
                label(sent, 7, str(number))
            for sent, received in ((30, 39), (55, 72)):
                arrow([(sent, 28), (received, 61)])
                dot(received, 66)
            line([(78, 28), (91, 58)], "muted", True)
            cross(91, 66)
            arrow([(24, 80), (96, 80)], "muted")
            label(87, 96, "시간")
        elif self.kind == "process":
            box(12, 28, 43, 24, "selection", "link")
            line([(55, 40), (92, 40)], "muted", True)
            line([(12, 55), (12, 70)], "muted")
            line([(55, 55), (55, 70)], "muted")
            cross(55, 40)
            label(22, 11, "실행")
            label(59, 11, "중단")
            arrow([(8, 70), (96, 70)], "muted")
            label(87, 90, "시간")
        elif self.kind == "robot":
            p.setPen(QPen(theme.qcolor("link"), 9))
            p.drawPolyline(QPolygonF([point(8, 70), point(36, 70), point(59, 25), point(91, 25)]))
            for x, y in ((36, 70), (59, 25)):
                p.setPen(QPen(theme.qcolor("link"), 2))
                p.setBrush(theme.qcolor("surface"))
                p.drawEllipse(point(x, y), 6, 6)
            label(19, 48, "링크")
            label(43, 91, "관절")
        elif self.kind == "reward":
            line([(7, 20), (7, 75), (96, 75)], "muted")
            line([(9, 67), (21, 51), (33, 61), (45, 36), (57, 48), (69, 26), (81, 35), (94, 22)])
            label(13, 7, "보상")
            label(88, 92, "반복")
        elif self.kind in ("curve", "signal", "response"):
            line([(5, 8), (5, 88)], "muted")
            arrow([(5, 88), (96, 88)], "muted")
            if self.kind == "curve":
                line([(7, 15), (20, 40), (36, 63), (54, 73), (76, 79), (95, 81)])
                line([(7, 22), (20, 47), (36, 60), (54, 67), (76, 61), (95, 48)], "muted", True)
            elif self.kind == "signal":
                line([(7, 56), (19, 40), (31, 63), (43, 45), (55, 12), (67, 53), (79, 46), (95, 56)])
            else:
                line([(7, 72), (25, 72), (25, 30), (95, 30)], "muted", True)
                line([(7, 72), (25, 72), (37, 57), (49, 24), (61, 20), (74, 33), (85, 30), (95, 30)])
        elif self.kind in ("map", "route", "recovery"):
            for x in range(10, 100, 16):
                line([(x, 5), (x, 95)], "line")
            for y in range(15, 100, 20):
                line([(2, y), (98, y)], "line")
            box(40, 40, 23, 43, "surface", "border_strong")
            if self.kind == "recovery":
                line([(8, 75), (28, 75), (48, 65)], "muted", True)
                cross(48, 65)
            arrow([(8, 75), (28, 75), (32, 22), (75, 22), (92, 65)])
            dot(8, 75)
            dot(92, 65)
        elif self.kind == "image":
            box(4, 8, 48, 82)
            line([(10, 71), (23, 32), (38, 32), (47, 71), (10, 71)], "muted")
            box(17, 24, 27, 53, "selection", "link")
            arrow([(58, 50), (70, 50)])
            for y, w in ((22, 22), (45, 10), (68, 6)):
                box(76, y, w, 13, "selection", "link")
        elif self.kind == "screen":
            box(3, 8, 58, 83)
            box(71, 8, 25, 83)
            for x, w in ((8, 48), (75, 17)):
                box(x, 20, w, 13, "selection", "link")
                box(x, 42, w, 18)
                box(x, 69, w, 10)
        elif self.kind == "table":
            for row in range(3):
                for col in range(4):
                    box(3 + col * 14, 12 + row * 26, 12, 22,
                        "selection" if row == 1 else "surface", "link" if row == 1 else "border")
            arrow([(64, 50), (74, 50)])
            for col in range(2):
                box(78 + col * 11, 38, 9, 24, "selection", "link")
        elif self.kind == "compare":
            for y in (15, 63):
                for x, w in ((4, 20), (34, 35), (80, 16)):
                    box(x, y, w, 22, "selection" if y == 63 else "surface")
            line([(50, 39), (50, 59)], "muted", True)
        elif self.kind == "deploy":
            for x in (4, 61):
                box(x, 12, 34, 77)
                for y in (23, 46, 69):
                    box(x + 5, y, 24, 12, "selection", "link")
            line([(40, 35), (58, 35)])
            line([(54, 29), (58, 35), (54, 41)])
            line([(58, 68), (40, 68)], "muted", True)
            line([(44, 62), (40, 68), (44, 74)], "muted")
        else:
            names = ("이벤트", "상태", "화면") if self.kind == "interaction" else (
                ("요청", "처리", "응답") if self.kind == "request" else ("입력", "계산", "출력"))
            for x in (3, 39, 75):
                box(x, 20, 22, 54, "selection", "link")
            for x, name in zip((14, 50, 86), names):
                label(x, 47, name)
            arrow([(25, 35), (38, 35)])
            arrow([(61, 35), (74, 35)])
            if self.kind == "request":
                arrow([(86, 78), (86, 90), (14, 90), (14, 78)], "muted", True)


class _Step(QWidget):
    def __init__(self, number, node, parent):
        super().__init__(parent)
        self.node = dict(node)
        label = node["label"]
        kind, description = EXAMPLES.get(label, ("pipeline", f"{label}의 입력과 처리 결과를 연결해 확인합니다."))
        self.title = kit.para(f"{number}. {label}", "body", bold=True)
        self.status = kit.para(COURSE_LABELS[node["course_status"]], "body", "secondary")
        self.status.setToolTip("ROKEY 11기 수업에서 다루는 범위입니다.")
        self.caption = kit.para(description, "body")
        for child in (self.title, self.status, self.caption):
            child.setParent(self)
            child.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.example = _Example(kind, f"{label}. {description}", self)
        self.setProperty("reading_anchor", True)
        _sizing(self)

    def _plan(self, width):
        inside = max(1, width - 32)
        status_width = min(inside // 2, math.ceil(QFontMetricsF(self.status.font()).horizontalAdvance(self.status.text())) + 2)
        title_width = max(1, inside - status_width - theme.GAP["title_description"])
        header = max(self.title.heightForWidth(title_width), self.status.heightForWidth(status_width))
        figure = max(112, theme.TYPE["body"][1] * 4)
        caption_y = 16 + header + theme.GAP["title_description"] + figure + theme.GAP["title_description"]
        return title_width, status_width, header, figure, caption_y

    def heightForWidth(self, width):
        *_, y = self._plan(width)
        return y + self.caption.heightForWidth(max(1, width - 32)) + 16

    def minimumSizeHint(self):
        return QSize(0, 0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._place()

    def _place(self):
        title_w, status_w, header, figure, caption_y = self._plan(self.width())
        self.title.setGeometry(16, 16, title_w, header)
        self.status.setGeometry(self.width() - 16 - status_w, 16, status_w, header)
        self.example.setGeometry(16, 16 + header + theme.GAP["title_description"], max(1, self.width() - 32), figure)
        self.caption.setGeometry(16, caption_y, max(1, self.width() - 32), self.height() - caption_y - 16)

    def refont(self):
        self._place()
        self.updateGeometry()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(theme.qcolor("border"), 1))
        painter.setBrush(theme.qcolor("surface"))
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(.5, .5, -.5, -.5), 12, 12)


class CareerLearningPath(QWidget):
    """원래 순서를 가로 행 또는 세로 열로 배치함."""
    def __init__(self, nodes=(), outputs=(), parent=None):
        super().__init__(parent)
        self.nodes = tuple(dict(node) for node in nodes)
        self.outputs = tuple(outputs)
        self.steps = [_Step(i, node, self) for i, node in enumerate(self.nodes, 1)]
        self.output = kit.para("산출물 예시\n" + "\n".join(self.outputs), "body")
        self.output.setContentsMargins(16, 16, 16, 16)
        self.output.setParent(self)
        self.output.setProperty("reading_anchor", True)
        self.output.setVisible(bool(self.outputs))
        self.columns = 1
        self.connections = []
        self.setAccessibleName("추천 학습 순서와 산출물 예시")
        self.setAccessibleDescription("단계 번호와 연결선은 추천 순서입니다. 상태는 수업 범위입니다. 그림은 설명용 예시입니다.")
        _sizing(self)

    def _geometry(self, width):
        gap = theme.GAP["section"]
        status_width = max((QFontMetricsF(step.status.font()).horizontalAdvance(step.status.text()) for step in self.steps), default=0)
        title_width = max((min(QFontMetricsF(step.title.font()).horizontalAdvance(step.title.text()),
                               QFontMetricsF(step.title.font()).horizontalAdvance("가" * 11)) for step in self.steps), default=0)
        minimum = max(300, math.ceil(status_width + title_width) + 48)
        columns = max(1, min(3, len(self.steps), (max(1, width - 32) + gap) // (minimum + gap)))
        cell = max(1, (width - 32 - gap * (columns - 1)) // columns)
        rects, y = [], 0
        for first in range(0, len(self.steps), columns):
            row = self.steps[first:first + columns]
            height = max(step.heightForWidth(cell) for step in row)
            rects.extend(QRect(16 + col * (cell + gap), y, cell, height) for col in range(len(row)))
            y += height + gap
        output = QRect(16, y, max(1, width - 32), self.output.heightForWidth(max(1, width - 32)))
        height = output.bottom() + 1 if self.outputs else (rects[-1].bottom() + 1 if rects else 0)
        return columns, rects, output, height

    def heightForWidth(self, width):
        return self._geometry(width)[-1]

    def sizeHint(self):
        return QSize(960, self.heightForWidth(960))

    def minimumSizeHint(self):
        return QSize(0, 0)

    def refont(self):
        self._place()
        self.updateGeometry()
        self.update()

    def _place(self):
        self.columns, rects, output, _ = self._geometry(self.width())
        for step, rect in zip(self.steps, rects):
            step.setGeometry(rect)
        self.output.setGeometry(output)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._place()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(theme.qcolor("muted"), 2))
        columns, rects, output, _ = self._geometry(self.width())
        if self.outputs:
            p.setBrush(theme.qcolor("surface"))
            p.setPen(QPen(theme.qcolor("border"), 1))
            p.drawRoundedRect(QRectF(output).adjusted(.5, .5, -.5, -.5), 12, 12)
            p.setPen(QPen(theme.qcolor("muted"), 2))
        self.connections = []
        for i, rect in enumerate(rects):
            if i + 1 < len(rects):
                following = rects[i + 1]
                if (i + 1) % columns:
                    points = [QPointF(rect.right() + 4, rect.center().y()),
                              QPointF(following.left() - 4, following.center().y())]
                elif columns > 1:
                    middle = (rect.bottom() + following.top()) / 2
                    points = [QPointF(rect.right() + 4, rect.center().y()),
                              QPointF(self.width() - 4, rect.center().y()), QPointF(self.width() - 4, middle),
                              QPointF(4, middle), QPointF(4, following.center().y()),
                              QPointF(following.left() - 4, following.center().y())]
                else:
                    points = [QPointF(rect.center().x(), rect.bottom() + 4),
                              QPointF(following.center().x(), following.top() - 8)]
            elif self.outputs:
                points = [QPointF(rect.center().x(), rect.bottom() + 4), QPointF(rect.center().x(), output.top() - 8)]
            else:
                continue
            self.connections.append((i, i + 1, tuple(points)))
            p.drawPolyline(QPolygonF(points))
            tip = points[-1]
            wings = [QPointF(-5, -5), QPointF(-5, 5)] if points[-2].x() < tip.x() else [QPointF(-5, -5), QPointF(5, -5)]
            for wing in wings:
                p.drawLine(tip, tip + wing)
