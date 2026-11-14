"""직무별 산출물의 모양을 고정된 합성 자료로 그리는 위젯임."""
from math import cos, pi, sin

from PyQt6.QtCore import QPointF, QRectF, QSize, Qt
from PyQt6.QtGui import QFontMetricsF, QPainter, QPen, QPolygonF
from PyQt6.QtWidgets import QSizePolicy, QWidget

from gui import theme


class _Plate:
    """도형은 그림 영역에 맞추고 글자와 선 굵기는 화면 단위로 유지함."""
    def __init__(self, painter, rect):
        self.p = painter
        self.rect = rect

    def point(self, x, y):
        r = self.rect
        return QPointF(r.left() + r.width() * x / 100, r.top() + r.height() * y / 100)

    def label(self, x, y, text, *, role="caption", color="ink", bold=False, align="center"):
        self.p.setFont(theme.font(role, bold))
        self.p.setPen(theme.qcolor(color))
        fm = QFontMetricsF(self.p.font(), self.p.device())
        width = fm.horizontalAdvance(text)
        offset = {"left": 0, "center": width / 2, "right": width}[align]
        origin = self.point(x, y) + QPointF(-offset, (fm.ascent() - fm.descent()) / 2)
        self.p.drawText(origin, text)

    def line(self, points, color="link", width=2, dashed=False):
        pen = QPen(theme.qcolor(color), width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        if dashed:
            pen.setStyle(Qt.PenStyle.DashLine)
        self.p.setPen(pen)
        self.p.setBrush(Qt.BrushStyle.NoBrush)
        self.p.drawPolyline(QPolygonF([self.point(x, y) for x, y in points]))

    def box(self, x1, y1, x2, y2, fill="surface_alt", edge=None, radius=4):
        self.p.setBrush(theme.qcolor(fill))
        self.p.setPen(QPen(theme.qcolor(edge), 1.5) if edge else Qt.PenStyle.NoPen)
        self.p.drawRoundedRect(QRectF(self.point(x1, y1), self.point(x2, y2)), radius, radius)

    def dot(self, x, y, radius, fill, edge=None):
        self.p.setPen(QPen(theme.qcolor(edge), 2) if edge else Qt.PenStyle.NoPen)
        self.p.setBrush(theme.qcolor(fill))
        self.p.drawEllipse(self.point(x, y), radius, radius)


def _control(g):
    g.label(0, 9, "각도(°)", role="micro", align="left")
    g.line([(34, 9), (42, 9)], "muted", dashed=True)
    g.label(44, 9, "목표", align="left")
    g.line([(68, 9), (76, 9)])
    g.label(78, 9, "측정", align="left")
    for angle in (0, 15, 30):
        y = 78 - angle * 1.5
        g.label(12, y, str(angle), align="right", role="micro")
        g.line([(15, y), (95, y)], "grid", 1)
    for second in (0, 1, 2):
        g.label(15 + 40 * second, 94, f"{second}초", role="micro")
    g.line([(15, 78), (35, 78), (35, 33), (95, 33)], "muted", 2, dashed=True)
    readings = ((0, 0), (.5, 0), (.625, 4), (.75, 13), (.875, 23), (1, 30),
                (1.125, 33), (1.25, 32), (1.5, 29), (1.75, 30), (2, 30))
    g.line([(15 + t * 40, 78 - a * 1.5) for t, a in readings], width=3)


def _navigation(g):
    for x in range(5, 100, 10):
        g.line([(x, 6), (x, 91)], "line", 1)
    for y in range(10, 91, 16):
        g.line([(4, y), (96, y)], "line", 1)
    g.box(35, 40, 65, 86, "surface_alt", "border_strong")
    g.label(50, 64, "장애물")
    g.line([(10, 68), (24, 68), (30, 23), (70, 23), (76, 68), (90, 68)], width=3)
    g.dot(10, 68, 4, "surface", "link")
    g.dot(90, 68, 5, "link")
    g.label(10, 91, "출발")
    g.label(90, 91, "도착")


def _vision(g):
    for x, name in ((26, "너트"), (74, "볼트")):
        # 부품 윤곽과 검출 상자를 같은 중심에 놓고 종횡비를 보존함.
        center = g.point(x, 58)
        size = min(g.rect.width() * .17, g.rect.height() * .31)
        p = g.p
        p.save()
        p.translate(center)
        p.scale(size, size)
        p.setBrush(theme.qcolor("surface_alt"))
        p.setPen(QPen(theme.qcolor("muted"), .055))
        if name == "너트":
            p.drawPolygon(QPolygonF([QPointF(.85*cos(i*pi/3), .85*sin(i*pi/3)) for i in range(6)]))
            p.setBrush(theme.qcolor("surface"))
            p.drawEllipse(QPointF(), .34, .34)
        else:
            p.save()
            p.rotate(28)
            p.drawRect(QRectF(-.20, -.47, .40, 1.24))
            for y in (.04, .23, .42, .61):
                p.drawLine(QPointF(-.20, y + .1), QPointF(.20, y))
            p.drawRoundedRect(QRectF(-.48, -.78, .96, .36), .06, .06)
            p.restore()
        p.setPen(QPen(theme.qcolor("link"), .045))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(QRectF(-1, -.94, 2, 1.88))
        p.restore()
        g.label(x, 12, name, bold=True)


def _field(g):
    for x, name in ((31, "로봇"), (85, "자동문")):
        g.label(x, 12, name, bold=True)
    for y, phase, state, tone in ((43, "조치 전", "단선", "wrong"), (80, "조치 후", "연결", "ok")):
        g.label(3, y, phase, align="left")
        if state == "연결":
            g.line([(31, y), (85, y)], tone)
        else:
            g.line([(31, y), (47, y)], tone, dashed=True)
            g.line([(69, y), (85, y)], tone, dashed=True)
        g.dot(31, y, 4, "surface", tone)
        g.dot(85, y, 4, "surface", tone)
        g.label(58, y - 11 if state == "연결" else y, state, color=tone, bold=True)


def _policy(g):
    for start, label, reached in ((0, "정책 A", False), (52, "정책 B", True)):
        g.box(start, 3, start + 48, 98)
        g.label(start + 24, 18, label, bold=True)
        x, y = start + 36, 52
        radius = min(g.rect.width() * .054, g.rect.height() * .14)
        g.dot(x, y, radius, "surface", "muted")
        end = (x, y) if reached else (start + 24, 58)
        g.line([(start + 7, 65), (start + 14, 62), (start + 20, 52), end])
        g.dot(*end, 4, "link")
        g.label(start + 24, 83, "도달" if reached else "미도달")


def _robot_backend(g):
    for x, label in ((18, "로봇"), (65, "관제 서버")):
        g.dot(x, 19, 4, "muted")
        g.line([(x, 23), (x, 93)], "border_strong", 1)
        g.label(x, 6, label, bold=True)
    for y, request, result in ((48, "17번 전송", "저장 1건"), (86, "17번 재전송", "추가 0건")):
        g.label(41, y - 14, request)
        g.line([(18, y), (65, y)])
        g.line([(62, y - 4), (65, y), (62, y + 4)])
        g.label(98, y, result, align="right")


def _platform(g):
    g.line([(16, 48), (84, 48)], "border_strong", 2)
    for x, version, state, tone in ((16, "v1", "운영 중", "muted"), (50, "v2", "점검 실패", "wrong"),
                                    (84, "v1", "복구", "ok")):
        g.label(x, 19, version, bold=True, role="label")
        g.dot(x, 48, 8, "surface", tone)
        g.dot(x, 48, 3, tone)
        g.label(x, 77, state, color=tone)


def _frontend(g):
    g.box(4, 4, 96, 96, "surface", "border_strong", 8)
    g.box(6, 7, 94, 43)
    g.label(10, 24, "상태 필터", align="left")
    g.label(89, 24, "오류만", align="right", bold=True)
    g.dot(12, 69, 5, "wrong")
    g.label(18, 69, "로봇 R-02", align="left", bold=True)
    g.label(90, 69, "연결 끊김", align="right", color="wrong")


def _backend(g):
    for y, permission, status in ((28, "권한 있음", "200"), (76, "권한 없음", "403")):
        g.line([(30, 52), (39, 52), (39, y), (46, y)], "border_strong")
        g.label(49, y, permission, align="left")
        g.box(80, y - 14, 99, y + 14)
        g.label(89.5, y, status, bold=True)
    g.box(1, 18, 31, 86, "selection")
    g.label(16, 38, "GET", bold=True, color="selection_ink")
    g.label(16, 65, "/tasks/7", color="selection_ink")


def _data(g):
    for x, label, count in ((16, "수집", 6), (50, "중복 제거 후", 4), (84, "재적재 후", 4)):
        g.label(x, 12, label, bold=True)
        for i in range(count):
            left = x - 9 + (i % 2) * 10
            bottom = 69 - (i // 2) * 13
            g.box(left, bottom - 10, left + 8, bottom, "link", radius=2)
        g.label(x, 87, f"{count}행")
    for x in (33, 67):
        g.line([(x - 3, 48), (x + 2, 48)], "border_strong")
        g.line([(x, 44), (x + 2, 48), (x, 52)], "border_strong")


def _qa(g):
    for x, title in ((17, "입력 길이"), (52, "기대"), (84, "실제")):
        g.label(x, 14, title, bold=True)
    g.line([(2, 29), (98, 29)], "grid", 1)
    for y, length, expected, observed in ((48, "7자", "거절", "허용"), (82, "8자", "허용", "허용")):
        g.label(17, y, length)
        g.label(52, y, expected)
        wrong = expected != observed
        if wrong:
            g.box(70, y - 14, 98, y + 14, "wrong_weak", "wrong")
        g.label(84, y, observed, color="wrong" if wrong else "ink", bold=wrong)


# 직무를 고른 즉시 오른쪽 본문과 접근성 설명에 같은 문장을 제공함.
_EXAMPLES = {
    "robot_control": ("관절 각도 응답", "목표 각도를 0도에서 30도로 바꾼 예시입니다. 측정 각도는 목표를 잠시 넘은 뒤 2초에 30도가 됩니다.", _control),
    "robot_navigation": ("장애물 우회 경로", "출발점과 도착점 사이에 장애물을 놓은 예시입니다. 주행 경로는 장애물 위쪽을 돌아 도착점에 닿습니다.", _navigation),
    "robot_vision": ("부품 검출 결과", "합성 영상에서 검출한 부품을 상자로 표시한 예시입니다. 왼쪽 상자에는 너트, 오른쪽 상자에는 볼트가 있습니다.", _vision),
    "field_integration": ("설비 통신 점검", "로봇과 자동문 사이의 통신선을 점검한 예시입니다. 조치 전에는 선이 끊어져 있고 조치 후에는 두 장치가 연결됩니다.", _field),
    "robot_policy": ("정책별 목표 도달 시험", "같은 출발점과 목표 영역에서 두 정책을 시험한 예시입니다. 정책 A의 끝점은 목표 원 밖에, 정책 B의 끝점은 원 안에 있습니다.", _policy),
    "robot_backend": ("중복 수신 기록", "로봇이 17번 메시지를 두 번 보낸 예시입니다. 관제 서버는 첫 수신 때 한 건을 저장하고 재수신 때는 추가로 저장하지 않습니다.", _robot_backend),
    "platform_infrastructure": ("배포 복구 이력", "v1 운영 중에 v2를 배포한 예시입니다. v2가 점검에 실패해 v1으로 되돌립니다.", _platform),
    "frontend": ("관제 화면의 오류 필터", "관제 화면에서 오류만 보도록 설정한 예시입니다. 목록에 로봇 R-02와 연결 끊김 상태가 표시됩니다.", _frontend),
    "backend": ("권한별 조회 응답", "로그인한 사용자가 GET /tasks/7로 작업을 조회하는 예시입니다. 읽기 권한이 있으면 HTTP 200, 없으면 HTTP 403을 돌려줍니다.", _backend),
    "data_engineering": ("중복 제거와 적재", "원본 6행에서 중복을 빼면 4행이 남는 예시입니다. 같은 기록 키로 다시 적재한 뒤에도 저장된 자료는 4행입니다.", _data),
    "qa": ("8자 이상 입력 검사", "8자 이상만 허용하는 입력란의 경계값 시험 예시입니다. 8자는 기대대로 허용되지만 거절해야 할 7자도 허용됩니다.", _qa),
}
_EMPTY = ("결과 예시", "표시할 결과 예시가 없습니다.", None)


class CareerArtifact(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        policy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)
        self.set_role(None)
        theme.signals.changed.connect(self.update)

    def set_role(self, role_id):
        self._title, description, self._draw = _EXAMPLES.get(role_id, _EMPTY)
        self.setAccessibleName(self._title + (" · 합성 예시" if self._draw else ""))
        self.setAccessibleDescription(description)
        self.update()

    def heightForWidth(self, width):
        return max(180, min(340, round(width / 2.1)))

    def sizeHint(self):
        return QSize(630, self.heightForWidth(630))

    def minimumSizeHint(self):
        return QSize(0, 180)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        frame = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        painter.setPen(QPen(theme.qcolor("border"), 1))
        painter.setBrush(theme.qcolor("surface"))
        painter.drawRoundedRect(frame, 12, 12)
        pad = max(12, min(24, self.width() * .035))
        area = frame.adjusted(pad, 0, -pad, 0)
        header = max(42, min(58, self.height() * .22))
        top = _Plate(painter, QRectF(area.left(), 1, area.width(), header))
        top.label(0, 50, self._title, role="label", bold=True, align="left")
        if self._draw:
            top.label(100, 50, "합성 예시", align="right", color="muted")
        top.line([(0, 100), (100, 100)], "grid", 1)
        body = _Plate(painter, area.adjusted(0, header + 10, 0, -12))
        if self._draw:
            self._draw(body)
        else:
            body.label(50, 50, self.accessibleDescription(), color="muted")
        painter.end()
