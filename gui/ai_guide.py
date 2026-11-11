# -*- coding: utf-8 -*-
"""실제 화면 PNG에 번호와 테두리를 겹쳐 그리는 사용 안내임.

manifest의 image는 같은 폴더 아래 PNG 경로임. targets의 x, y, width, height는
원본 PNG 픽셀 좌표이며 label은 번호 아래에서 읽는 설명임. 학습 서비스는 호출하지 않음.
"""
import json
import math
from pathlib import Path

from PyQt6.QtCore import QRectF, QSize, Qt, QTimer
from PyQt6.QtGui import QPainter, QPen, QPixmap, QTextCursor
from PyQt6.QtWidgets import (QAbstractScrollArea, QApplication, QDialog, QHBoxLayout,
                             QLineEdit, QPlainTextEdit, QScrollArea, QSizePolicy,
                             QTextEdit, QWidget)

from gui import ai_text, kit, theme

MANIFEST = Path(__file__).with_name("guide") / "ai" / "manifest.json"


class GuideError(ValueError):
    """안내 자료를 읽지 못했음을 구별함."""


def load_steps(manifest):
    """안내 문장과 원본 좌표를 읽음. 폴더 밖의 이미지와 잘못된 좌표를 거부함."""
    path = Path(manifest).resolve()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError()
        steps = data["steps"]
        if data.get("version") != 1 or not isinstance(steps, list) or not 1 <= len(steps) <= 5:
            raise ValueError()
        result, ids = [], set()
        for step in steps:
            sid, title, description = step["id"], step["title"], step["description"]
            if not all(isinstance(v, str) and v.strip() for v in (sid, title, description)) or sid in ids:
                raise ValueError()
            ids.add(sid)
            if not isinstance(step["image"], str) or ":" in step["image"]:
                raise ValueError()
            image = (path.parent / step["image"]).resolve()
            if not image.is_relative_to(path.parent) or image.suffix.lower() != ".png":
                raise ValueError()
            targets = step["targets"]
            if not isinstance(targets, list) or not 1 <= len(targets) <= 8:
                raise ValueError()
            checked = []
            for target in targets:
                rect = [target[k] for k in ("x", "y", "width", "height")]
                if not all(type(v) in (int, float) and math.isfinite(v) for v in rect):
                    raise ValueError()
                if min(rect[:2]) < 0 or min(rect[2:]) <= 0 or not isinstance(target["label"], str):
                    raise ValueError()
                checked.append({"rect": QRectF(*rect), "label": target["label"]})
            result.append({"id": sid, "title": title, "description": description,
                           "image": image, "targets": checked})
        return result
    except (OSError, UnicodeError, ValueError, TypeError, KeyError) as error:
        raise GuideError("안내 화면을 읽지 못했습니다. 최신 파일을 받은 뒤 다시 열어 주세요.") from error


class ViewState:
    """모달을 열기 전 초점·선택·스크롤을 메모리에 보관함."""

    def __init__(self, owner):
        self.owner = owner
        focus = QApplication.focusWidget()
        self.focus = focus if focus is not None and (focus is owner or owner.isAncestorOf(focus)) else None
        self.selection = None
        if isinstance(self.focus, QLineEdit):
            self.selection = (self.focus.selectionStart(), len(self.focus.selectedText()), self.focus.cursorPosition())
        elif isinstance(self.focus, (QTextEdit, QPlainTextEdit)):
            self.selection = QTextCursor(self.focus.textCursor())
        self.scrolls = [(area, area.horizontalScrollBar().value(), area.verticalScrollBar().value())
                        for area in owner.findChildren(QAbstractScrollArea)]

    def restore(self):
        """모달이 닫힌 뒤 입력 선택을 먼저 복원하고 읽던 위치를 마지막에 돌림."""
        try:
            self.owner.activateWindow()
            if isinstance(self.focus, QLineEdit) and self.selection is not None:
                start, length, cursor = self.selection
                if start >= 0:
                    if cursor == start:
                        self.focus.setSelection(start + length, -length)
                    else:
                        self.focus.setSelection(start, length)
                else:
                    self.focus.setCursorPosition(cursor)
            elif isinstance(self.focus, (QTextEdit, QPlainTextEdit)) and self.selection is not None:
                self.focus.setTextCursor(self.selection)
            if self.focus is not None:
                self.focus.setFocus(Qt.FocusReason.OtherFocusReason)
            for area, horizontal, vertical in self.scrolls:
                area.horizontalScrollBar().setValue(horizontal)
                area.verticalScrollBar().setValue(vertical)
        except RuntimeError:
            pass  # 안내를 닫기 전에 원래 창을 닫았으면 복원하지 않음


class ScreenshotView(QWidget):
    """PNG의 비율을 유지하고 원본 좌표를 표시 좌표로 옮겨 그림."""

    def __init__(self, step, fit=True, parent=None):
        super().__init__(parent)
        self.step, self.fit, self.zoom = step, fit, 1.0
        self.pixmap = QPixmap(str(step["image"]))
        self.pixmap.setDevicePixelRatio(1.0)
        self.error = ""
        if self.pixmap.isNull():
            self.error = "안내 이미지를 읽지 못했습니다. 창을 닫고 다시 열어 주세요."
        elif any(not QRectF(self.pixmap.rect()).contains(t["rect"]) for t in step["targets"]):
            self.error = "강조할 위치가 이미지 범위를 벗어났습니다. 최신 파일을 받은 뒤 다시 열어 주세요."
        self.setAccessibleName("번호로 표시한 사용 안내 화면")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setMinimumHeight(200 if fit else 0)
        if not fit:
            self.set_zoom(1.0)
        theme.signals.changed.connect(self.update)

    def sizeHint(self):
        if self.pixmap.isNull():
            return QSize(640, 200)
        return QSize(800, round(800 * self.pixmap.height() / self.pixmap.width()))

    def hasHeightForWidth(self):
        return self.fit

    def heightForWidth(self, width):
        return max(200, round(width * self.pixmap.height() / max(1, self.pixmap.width())))

    def set_zoom(self, zoom):
        self.zoom = min(3.0, max(0.5, zoom))
        self.setFixedSize(max(1, round(self.pixmap.width() * self.zoom)),
                          max(1, round(self.pixmap.height() * self.zoom)))
        self.update()

    def image_rect(self):
        if self.pixmap.isNull():
            return QRectF()
        scale = min(self.width() / self.pixmap.width(), self.height() / self.pixmap.height())
        w, h = self.pixmap.width() * scale, self.pixmap.height() * scale
        return QRectF((self.width() - w) / 2, (self.height() - h) / 2, w, h)

    def target_rect(self, target):
        image = self.image_rect()
        scale = image.width() / max(1, self.pixmap.width())
        rect = target["rect"]
        return QRectF(image.x() + rect.x() * scale, image.y() + rect.y() * scale,
                      rect.width() * scale, rect.height() * scale)

    def badge_rect(self, target):
        image, rect = self.image_rect(), self.target_rect(target)
        radius = max(15, theme.TYPE["label"][0])
        x = min(max(rect.left() + radius, image.left() + radius), image.right() - radius)
        y = min(max(rect.center().y(), image.top() + radius), image.bottom() - radius)
        centers = [(rect.left() - radius - 4, y), (rect.right() + radius + 4, y),
                   (x, rect.top() - radius - 4), (x, rect.bottom() + radius + 4)]
        for cx, cy in centers:
            candidate = QRectF(cx - radius, cy - radius, 2 * radius, 2 * radius)
            if image.contains(candidate) and not any(candidate.intersects(self.target_rect(other))
                                                     for other in self.step["targets"]):
                return candidate
        return QRectF(x - radius, y - radius, 2 * radius, 2 * radius)

    def paintEvent(self, event):
        if self.error:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        image = self.image_rect()
        painter.drawPixmap(image, self.pixmap, QRectF(self.pixmap.rect()))
        painter.setFont(theme.font("label", True))
        for number, target in enumerate(self.step["targets"], 1):
            rect = self.target_rect(target)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(theme.qcolor("surface"), 7))
            painter.drawRoundedRect(rect.adjusted(2, 2, -2, -2), 6, 6)
            painter.setPen(QPen(theme.qcolor("primary"), 3))
            painter.drawRoundedRect(rect.adjusted(2, 2, -2, -2), 6, 6)
            badge = self.badge_rect(target)
            painter.setPen(QPen(theme.qcolor("surface"), 2))
            painter.setBrush(theme.qcolor("primary"))
            painter.drawEllipse(badge)
            painter.setPen(theme.qcolor("primary_ink"))
            painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, str(number))


def _dialog_size(dialog, owner):
    """작은 부모 창과 작업 영역 안에 대화상자를 맞춤."""
    room = owner.screen().availableGeometry()
    dialog.resize(min(1040, owner.width(), room.width() - 32),
                  min(760, owner.height(), room.height() - 32))


class ImageDialog(QDialog):
    """원본 크기부터 스크롤하며 보고 더 확대하는 창임."""

    def __init__(self, parent, step):
        self.return_state = ViewState(parent)
        super().__init__(parent)
        kit.page(self)
        self.setWindowTitle("안내 화면 크게 보기")
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        box = kit.box(self, (24, 24, 24, 24), theme.GAP["paragraph"])
        heading = kit.para(step["title"], "headline")
        box.addWidget(heading)
        self.view = ScreenshotView(step, fit=False)
        self.scroll = QScrollArea()
        self.scroll.setWidget(self.view)
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        box.addWidget(self.scroll, 1)
        controls = QHBoxLayout()
        controls.setSpacing(theme.GAP["detail"])
        self.minus = kit.button("축소", scale="l")
        self.percent = kit.label("100%", "label")
        self.plus = kit.button("확대", scale="l")
        self.close_btn = kit.button("닫기", scale="l")
        for widget in (self.minus, self.percent, self.plus):
            controls.addWidget(widget)
        controls.addStretch(1)
        controls.addWidget(self.close_btn)
        box.addLayout(controls)
        self.minus.clicked.connect(lambda: self.change_zoom(-0.25))
        self.plus.clicked.connect(lambda: self.change_zoom(0.25))
        self.close_btn.clicked.connect(self.close)
        self.finished.connect(lambda: QTimer.singleShot(0, self.return_state.restore))
        _dialog_size(self, parent)

    def change_zoom(self, delta):
        self.view.set_zoom(self.view.zoom + delta)
        self.percent.setText("%d%%" % round(self.view.zoom * 100))
        self.minus.setEnabled(self.view.zoom > 0.5)
        self.plus.setEnabled(self.view.zoom < 3)


class GuideDialog(QDialog):
    """안내 단계만 넘김. 학습 화면이나 학습 기록은 바꾸지 않음."""

    def __init__(self, parent, manifest=MANIFEST):
        self.return_state = ViewState(parent.window())
        super().__init__(parent.window())
        kit.page(self)
        self.setWindowTitle("학습·사용 안내")
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.position, self.image, self.large_dialog = 0, None, None
        self.error = ""
        try:
            self.steps = load_steps(manifest)
        except GuideError as error:
            self.steps, self.error = [], str(error)
        box = kit.box(self, (24, 24, 24, 24), theme.GAP["description_content"])
        self.heading = kit.para("학습·사용 안내", "headline")
        box.addWidget(self.heading)
        self.content = QWidget()
        self.content_box = kit.box(self.content, spacing=theme.GAP["paragraph"])
        self.scroll = kit.scroll(self.content)
        box.addWidget(self.scroll, 1)
        self.controls = QWidget()
        row = kit.box(self.controls, spacing=theme.GAP["detail"], horizontal=True)
        self.large_btn = kit.button("크게 보기", scale="l")
        self.previous = kit.button("이전", scale="l")
        self.counter = kit.label("", "label")
        self.next_btn = kit.button("다음", "primary", "l")
        self.close_btn = kit.button("닫기", scale="l")
        row.addWidget(self.large_btn)
        row.addStretch(1)
        for widget in (self.previous, self.counter, self.next_btn, self.close_btn):
            row.addWidget(widget)
        box.addWidget(self.controls)
        self.previous.clicked.connect(lambda: self.show_step(self.position - 1))
        self.next_btn.clicked.connect(lambda: self.show_step(self.position + 1))
        self.close_btn.clicked.connect(self.close)
        self.large_btn.clicked.connect(self.enlarge)
        self.finished.connect(lambda: QTimer.singleShot(0, self.return_state.restore))
        self.show_step(0)
        _dialog_size(self, parent.window())

    def show_step(self, position):
        if self.steps and not 0 <= position < len(self.steps):
            return
        self.position = position
        while self.content_box.count():
            item = self.content_box.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()
        self.image = None
        if self.steps:
            step = self.steps[position]
            title = kit.para(step["title"], "title")
            self.content_box.addWidget(kit.heading(title, kit.para(step["description"], "body")))
            self.image = ScreenshotView(step)
            self.content_box.addWidget(self.image)
            if self.image.error:
                self.content_box.addWidget(kit.para(self.image.error, "body", "danger"))
                self.image.hide()
            legend = "\n".join("%d. %s" % (n, t["label"]) for n, t in enumerate(step["targets"], 1))
            self.content_box.addWidget(kit.para(legend, "body"))
        else:
            self.content_box.addWidget(kit.para("\n\n".join(ai_text.STEPS), "body"))
            self.content_box.addWidget(kit.para(self.error, "body", "secondary"))
        self.counter.setText("%d / %d" % (position + 1, len(self.steps)) if self.steps else "")
        self.previous.setEnabled(bool(self.steps) and position > 0)
        self.next_btn.setEnabled(position + 1 < len(self.steps))
        self.large_btn.setEnabled(self.image is not None and not self.image.error)
        self.scroll.verticalScrollBar().setValue(0)

    def enlarge(self):
        if self.image is None or self.image.error:
            return
        self.large_dialog = ImageDialog(self, self.steps[self.position])
        self.large_dialog.finished.connect(lambda: setattr(self, "large_dialog", None))
        self.large_dialog.open()


def open_guide(parent, manifest=MANIFEST):
    """같은 창의 안내를 한 번만 열고 닫은 뒤 입력 상태를 복원함."""
    current = getattr(parent, "_ai_guide_dialog", None)
    if current is not None:
        current.raise_()
        return current
    dialog = GuideDialog(parent, manifest)
    parent._ai_guide_dialog = dialog
    dialog.finished.connect(lambda: setattr(parent, "_ai_guide_dialog", None))
    dialog.open()
    return dialog
