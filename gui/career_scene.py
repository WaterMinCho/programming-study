"""직무별 업무 장면과 결과 예시를 같은 자리에서 비교함."""
from pathlib import Path

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QPainter, QPainterPath, QPixmap
from PyQt6.QtWidgets import QSizePolicy, QWidget

from gui import kit, theme
from gui.career_artifact import CareerArtifact


SCENES = Path(__file__).resolve().parents[1] / "career" / "scenes"

# 카탈로그의 업무와 연결한 실습 예시이며 실제 기업의 현장을 묘사한 것이 아님.
STORIES = {
    "robot_control": ("로봇 팔이 원하는 각도에서 멈출까요?", "모터에 목표 각도를 보내고 센서가 읽은 각도와 비교합니다. 두 값이 언제 벌어지는지 알면 제어 동작을 어디부터 점검할지 정할 수 있습니다."),
    "robot_navigation": ("통로에 상자가 놓이면 어디로 갈까요?", "목적지는 그대로지만 원래 경로는 막혔습니다. 로봇의 현재 위치와 장애물 위치를 지도에 놓고 지나갈 수 있는 경로를 찾습니다."),
    "robot_vision": ("카메라는 너트와 볼트를 구분할 수 있을까요?", "컨베이어 위의 부품을 카메라로 촬영합니다. 검출 상자가 각 부품을 잘 감싸는지, 붙은 이름이 맞는지 확인합니다."),
    "field_integration": ("로봇과 설비 사이에 신호가 통할까요?", "현장에서는 로봇이 목적지에 가는 것만으로 설치가 끝나지 않습니다. 로봇의 도착 신호가 설비에 전달되고 다음 동작으로 이어지는지 시험합니다."),
    "robot_policy": ("두 제어 정책 중 어느 쪽이 목표에 닿을까요?", "시뮬레이터에 목표 위치를 정해 두고 로봇을 움직여 봅니다. 같은 출발점에서 두 정책으로 움직인 궤적을 비교합니다."),
    "robot_backend": ("같은 상태 신호가 두 번 도착하면 어떻게 셀까요?", "여러 로봇이 정지·이동 상태를 관제 서버에 보냅니다. 연결이 끊겼다 돌아온 뒤에도 같은 기록이 두 번 쌓이지 않는지 확인합니다."),
    "platform_infrastructure": ("배포 직후 오류가 늘면 어떻게 되돌릴까요?", "새 버전을 일부 서버에 먼저 적용하고 상태를 지켜봅니다. 문제가 생기면 이전 버전으로 되돌린 뒤 서비스가 회복됐는지 확인합니다."),
    "frontend": ("관제 화면에서 멈춘 로봇을 바로 찾을 수 있을까요?", "서버가 보내는 상태를 화면에 표시합니다. 화면 폭이 좁거나 연결이 끊겨도 사용자가 지금 확인할 로봇을 찾을 수 있게 구성합니다."),
    "backend": ("누가 요청하느냐에 따라 응답이 어떻게 달라질까요?", "화면에서 보낸 조회 요청을 받아 권한을 확인하고 저장된 자료를 찾습니다. 정상 요청과 권한이 없는 요청이 각각 어떤 응답을 받는지 비교합니다."),
    "data_engineering": ("같은 기록을 다시 넣어도 결과가 같을까요?", "센서에서 받은 기록을 정리하고 검사한 뒤 저장합니다. 누락이나 중복 때문에 과거 자료를 다시 처리해도 집계가 달라지지 않는지 살펴봅니다."),
    "qa": ("8자 이상인 입력란에 7자를 넣으면 어떻게 될까요?", "제품의 요구사항을 시험 조건으로 옮깁니다. 기대한 결과와 실제 결과가 다르면 다른 사람도 같은 문제를 다시 확인할 수 있게 조건을 기록합니다."),
}


class ScenePicture(QWidget):
    def __init__(self):
        super().__init__()
        self.pixmap = QPixmap()
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)

    def set_scene(self, role_id):
        self.pixmap = QPixmap(str(SCENES / f"{role_id}.webp")) if role_id in STORIES else QPixmap()
        self.update()

    def paintEvent(self, event):
        if self.pixmap.isNull():
            return
        rect = QRectF(self.rect())
        if rect.isEmpty():
            return
        source = QRectF(self.pixmap.rect())
        scale = max(rect.width() / source.width(), rect.height() / source.height())
        width, height = rect.width() / scale, rect.height() / scale
        crop = QRectF((source.width() - width) / 2, (source.height() - height) / 2, width, height)
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        clip = QPainterPath()
        clip.addRoundedRect(rect, theme.RADIUS["control"], theme.RADIUS["control"])
        painter.setClipPath(clip)
        painter.drawPixmap(rect, self.pixmap, crop)


class RoleScene(QWidget):
    def __init__(self):
        super().__init__()
        self.role = None
        self.view_index = 0
        self.has_picture = self.has_artifact = False
        self.wide = False
        self.question = self.story = ""
        outer = kit.box(self, spacing=theme.GAP["paragraph"])
        self.tabs = kit.TabBar(("업무 장면", "결과 예시"))
        self.tabs.setAccessibleName("직무 그림 선택")
        self.tabs.layout().itemAt(0).layout().setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.tabs, 0, Qt.AlignmentFlag.AlignLeft)

        panels = QWidget()
        self.panels = kit.box(panels, spacing=theme.GAP["paragraph"], horizontal=True)
        self.picture = ScenePicture()
        self.artifact = CareerArtifact()
        self.panels.addWidget(self._panel("업무 장면", self.picture), 1)
        self.panels.addWidget(self._panel("결과 예시", self.artifact), 1)
        outer.addWidget(panels)

        self.title = kit.para("", "headline", bold=True)
        self.title.setProperty("reading_anchor", True)
        self.caption = kit.para("", "body", "secondary")
        outer.addWidget(kit.heading(self.title, self.caption))
        self.tabs.picked.connect(self.show_view)

    @staticmethod
    def _panel(title, visual):
        panel = QWidget()
        layout = kit.box(panel, spacing=theme.GAP["detail"])
        layout.addWidget(kit.para(title, "label", "secondary", bold=True))
        layout.addWidget(visual)
        return panel

    def _place(self):
        self.wide = self.width() >= max(820, self.fontMetrics().height() * 42)
        compare = self.wide and self.has_picture and self.has_artifact
        self.tabs.setVisible(not self.wide and self.has_picture and self.has_artifact)
        width = (self.width() - self.panels.spacing()) / 2 if compare else self.width()
        height = round(max(180, min(335, width / 2.35)))
        for number, (visual, available) in enumerate(((self.picture, self.has_picture), (self.artifact, self.has_artifact))):
            panel = self.panels.itemAt(number).widget()
            panel.setVisible(available and (self.wide or number == self.view_index))
            panel.layout().itemAt(0).widget().setVisible(self.wide)
            visual.setFixedHeight(height)
        if self.role:
            result = self.artifact.accessibleDescription()
            text = result if self.view_index == 1 and not compare and self.has_artifact else self.story
            if text != self.caption.text():
                self.caption.setText(text)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._place()

    def refont(self):
        self._place()

    def set_role(self, role):
        key = role["id"]
        self.role = role
        self.question, self.story = STORIES.get(key, (role["title"], " ".join(role["tasks"])))
        self.title.setText(self.question)
        self.picture.set_scene(key)
        self.has_picture = not self.picture.pixmap.isNull()
        self.has_artifact = key in STORIES
        self.artifact.set_role(key)
        self.picture.setAccessibleName(role["title"] + " 업무 장면")
        self.picture.setAccessibleDescription(self.story)
        self.show_view(self.tabs.group.checkedId())

    def show_view(self, index):
        # 그림 파일이 없더라도 사용자가 마지막으로 고른 탭은 보존함.
        self.view_index = index if self.has_picture else 1
        self.tabs.set_current(index)
        self._place()
