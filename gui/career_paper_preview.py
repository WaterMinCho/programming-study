"""논문 해설의 대표 도식을 로컬에서 재사용하고 상세 열기만 요청함."""
from PyQt6.QtCore import QRectF, QSize, Qt
from PyQt6.QtGui import QPainter, QPen
from PyQt6.QtWidgets import QAbstractButton, QSizePolicy, QWidget

from gui import kit, theme
from gui.paper_explainer import PAPER_IDS, PaperDiagram

PREVIEW_STAGES = {"paper-mobilenetv4": 1, "paper-convnext-v2": 0, "paper-dinov2": 0,
                  "paper-sam2": 0, "paper-dora-weight-decomposed": 0}


class PaperPreview(QAbstractButton):
    """현재 글꼴과 가용 폭으로 대표 단계의 그림 또는 기존 대체 설명을 표시함."""
    def __init__(self, paper, explanation=None, parent=None):
        super().__init__(parent)
        self.paper = paper
        self.stage = PREVIEW_STAGES.get(paper.paper_id, 0)
        self.diagram = None
        self.setAccessibleName(f"{paper.title} 그림 설명 보기")
        self.setToolTip("그림 설명 보기")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        policy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)
        self.setMinimumWidth(0)
        inset = theme.GAP["title_description"]
        box = kit.box(self, (inset, inset, inset, inset), theme.GAP["detail"])
        if explanation and paper.paper_id in PAPER_IDS:
            self.diagram = PaperDiagram(paper.paper_id, self)
            step = explanation["steps"][self.stage]
            description = step["shape"] + "\n" + step["text"]
            self.diagram.set_stage(self.stage, description)
            box.addWidget(self.diagram)
        else:
            box.addWidget(kit.para("대표 그림을 표시할 수 없습니다.", "caption", "secondary"))
            description = "\n".join(paper.figure_description) or paper.beginner_explanation
            box.addWidget(kit.para(description))
        self.setAccessibleDescription(description)
        for child in self.findChildren(QWidget):
            child.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            child.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self.layout().totalHeightForWidth(max(1, width))

    def minimumSizeHint(self):
        return QSize(0, 0)

    def sizeHint(self):
        return QSize(680, self.heightForWidth(680))

    def refont(self):
        for index in range(self.layout().count()):
            kit.refont(self.layout().itemAt(index).widget())
        self._fit_height()
        self.update()

    def _fit_height(self):
        self.layout().invalidate()
        self.setFixedHeight(self.heightForWidth(self.width()))
        self.updateGeometry()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit_height()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if not event.isAutoRepeat():
                self.click()
            event.accept()
        else:
            super().keyPressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        edge = "focus" if self.hasFocus() else "link" if self.underMouse() and self.isEnabled() else "line"
        painter.setPen(QPen(theme.qcolor(edge), 2 if edge != "line" else 1))
        painter.setBrush(theme.qcolor("surface_alt"))
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1),
                                theme.RADIUS["control"], theme.RADIUS["control"])
