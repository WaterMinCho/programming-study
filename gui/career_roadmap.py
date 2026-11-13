"""직무를 탐색하고 선택 의도만 콜백으로 전달함. 개인 기록은 쓰지 않음."""
import math
from pathlib import Path

from PyQt6.QtCore import QEvent, QPoint, QPointF, QRectF, QSize, QSizeF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QPainter, QPen, QPixmap, QTextLayout, QTextOption
from PyQt6.QtWidgets import (QComboBox, QDialog, QGridLayout, QLabel, QScrollArea, QSizePolicy, QWidget)

from career.catalog import COURSE_LABELS, RELATION_LABELS, load_catalog
from gui import kit, motion, theme
from gui.dialog_layout import DialogLayout


def flow_buttons(*buttons):
    """글자 폭을 유지하고 같은 줄 단추의 세로 가운데를 맞춤."""
    out = QWidget()
    flow = kit.FlowLayout(out, spacing=theme.GAP["detail"])
    for button in buttons:
        flow.addWidget(button)
    return out


def clear_layout(layout):
    while layout.count():
        item = layout.takeAt(0)
        if item.widget() is not None:
            item.widget().hide()
            item.widget().deleteLater()


class CareerFilters(QWidget):
    """산업·제품을 넓을 때 나란히 놓고 세부 직무에는 한 줄 폭을 줌."""
    def __init__(self, groups):
        super().__init__()
        self.groups = groups
        self.wide = None
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(24)
        self._place()

    def _place(self):
        wide = self.width() >= theme.TYPE["body"][0] * 32 + 24
        if self.wide == wide:
            return
        self.wide = wide
        for group in self.groups:
            self.grid.removeWidget(group)
        self.grid.addWidget(self.groups[0], 0, 0)
        self.grid.addWidget(self.groups[1], 0 if wide else 1, 1 if wide else 0)
        self.grid.addWidget(self.groups[2], 1 if wide else 2, 0, 1, 2 if wide else 1)
        self.grid.setColumnStretch(0, 1)
        self.grid.setColumnStretch(1, 1 if wide else 0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._place()

    def refont(self):
        self._place()


class ReadingPage(QWidget):
    """화면 설정과 왕복 때 현재 문단의 화면 위치를 보관함."""
    def __init__(self, parent=None, on_back=None):
        super().__init__(parent)
        kit.page(self)
        self.setObjectName("page")
        self._anchor = None
        self._settling = False
        self._signature = None
        self._passes = 0
        outer = kit.box(self)
        self.top = kit.TopBar("← 커리어", plain=True)
        self.top.row.addStretch(1)
        self.top.setVisible(on_back is not None)
        self.top.back.setVisible(on_back is not None)
        if on_back:
            self.top.back.clicked.connect(on_back)
        outer.addWidget(self.top)
        self.content = QWidget()
        self.body = kit.box(self.content, (0, 24, 0, 48))
        column = kit.column(self.content)
        column.setContentsMargins(kit.MARGIN, 0, kit.MARGIN, 0)
        self.scroll = kit.scroll(column)
        outer.addWidget(self.scroll, 1)
        self.scroll.verticalScrollBar().valueChanged.connect(self._remember)
        self.scroll.verticalScrollBar().rangeChanged.connect(self._schedule_restore)
        self.scroll.viewport().installEventFilter(self)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._restore)
        theme.signals.changed.connect(self._appearance_changed)

    def _appearance_changed(self):
        kit.refont(self)
        self.update()

    def _remember(self, *_):
        if self._settling:
            return
        viewport = self.scroll.viewport()
        candidates = []
        for child in self.content.findChildren(QWidget):
            if child.property("reading_anchor") and child.isVisibleTo(self.content):
                top = child.mapTo(viewport, QPoint(0, 0)).y()
                if top + child.height() > 0:
                    candidates.append((abs(top), child, top))
        if candidates:
            _, child, top = min(candidates, key=lambda row: row[0])
            self._anchor = child, top

    def _schedule_restore(self, *_):
        if self._anchor is None or not hasattr(self, "_timer"):
            return
        self._settling = True
        self._passes = 0
        self._signature = None
        self._timer.start(0)

    def _restore(self):
        self._passes += 1
        bar = self.scroll.verticalScrollBar()
        signature = (self.content.size(), bar.maximum(), self.scroll.viewport().size())
        if signature != self._signature and self._passes < 24:
            self._signature = signature
            self._timer.start(0)
            return
        try:
            child, top = self._anchor
            if child.isVisibleTo(self.content):
                offset = child.mapTo(self.scroll.viewport(), QPoint(0, 0)).y() - top
                bar.setValue(bar.value() + offset)
        except (TypeError, RuntimeError):
            self._anchor = None
        self._settling = False
        self._remember()

    def refont(self):
        self._schedule_restore()

    def eventFilter(self, target, event):
        if target is self.scroll.viewport() and event.type() == QEvent.Type.Resize:
            self._schedule_restore()
        return super().eventFilter(target, event)

    def showEvent(self, event):
        super().showEvent(event)
        self._schedule_restore()

    def hideEvent(self, event):
        self._remember()
        super().hideEvent(event)

    def add_section(self, title, description=""):
        self.body.addSpacing(theme.GAP["section"])
        head = kit.para(title, "headline")
        head.setProperty("reading_anchor", True)
        self.body.addWidget(kit.heading(head, kit.para(description, "body", "secondary")) if description else head)
        self.body.addSpacing(theme.GAP["description_content"])


def _layout_text(text, role, width, bold=False):
    layout = QTextLayout(text.replace("\n", "\u2028"), theme.font(role, bold))
    option = QTextOption()
    option.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
    layout.setTextOption(option)
    layout.beginLayout()
    y = 0
    while True:
        line = layout.createLine()
        if not line.isValid():
            break
        line.setLineWidth(max(1, width))
        line.setPosition(QPointF(0, y))
        y += max(theme.TYPE[role][1], math.ceil(line.height()))
    layout.endLayout()
    return layout, y


class CareerFlow(QWidget):
    """입력·업무·산출물의 연결을 그림. 좁으면 연결 방향을 세로로 바꿈."""
    def __init__(self, nodes=(), parent=None):
        super().__init__(parent)
        self.nodes = tuple(nodes)
        self.node_rects = []
        self.text_rects = []
        self.setAccessibleName("업무 흐름")
        policy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)

    def set_nodes(self, nodes):
        self.nodes = tuple(nodes)
        self.setAccessibleDescription(". ".join(f"{title}: {text}" for title, text in self.nodes))
        self.updateGeometry()
        self.update()

    def _geometry(self, width):
        count = max(1, len(self.nodes))
        # 본문 글자 폭에 따라 가로 배치에 필요한 너비를 정함.
        horizontal = (width - 48 * (count - 1)) / count >= theme.TYPE["body"][0] * 12
        node_width = (width - 48 * (count - 1)) / count if horizontal else width - 32
        plans = []
        for title, text in self.nodes:
            title_layout, title_height = _layout_text(title, "body", node_width - 32, True)
            text_layout, text_height = _layout_text(text, "body", node_width - 32)
            plans.append((title_layout, title_height, text_layout, text_height))
        heights = [32 + title_h + 12 + text_h for _, title_h, _, text_h in plans]
        if horizontal:
            height = max(heights, default=0)
            rects = [QRectF(i * (node_width + 48), 0, node_width, height) for i in range(len(plans))]
        else:
            rects, y = [], 0
            for height in heights:
                rects.append(QRectF(32, y, node_width, height))
                y += height + 24
        return horizontal, rects, plans

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        _, rects, _ = self._geometry(max(96, width))
        return math.ceil(rects[-1].bottom()) + 1 if rects else 0

    def sizeHint(self):
        return QSize(960, self.heightForWidth(960))

    def minimumSizeHint(self):
        return QSize(0, 0)

    def refont(self):
        self.updateGeometry()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        horizontal, rects, plans = self._geometry(self.width())
        self.node_rects, self.text_rects = rects, []
        for index, (rect, plan) in enumerate(zip(rects, plans)):
            if index:
                previous = rects[index - 1]
                painter.setPen(QPen(theme.qcolor("link"), 2))
                if horizontal:
                    a, b = QPointF(previous.right() + 8, rect.center().y()), QPointF(rect.left() - 8, rect.center().y())
                    painter.drawLine(a, b)
                    painter.drawLine(b, b + QPointF(-6, -6))
                    painter.drawLine(b, b + QPointF(-6, 6))
                else:
                    painter.drawLine(QPointF(12, previous.center().y()), QPointF(12, rect.center().y()))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(theme.qcolor("surface_alt"))
            painter.drawRoundedRect(rect, 12, 12)
            if not horizontal:
                painter.setBrush(theme.qcolor("link"))
                painter.drawEllipse(QPointF(12, rect.center().y()), 4, 4)
                painter.setPen(QPen(theme.qcolor("link"), 2))
                painter.drawLine(QPointF(16, rect.center().y()), QPointF(24, rect.center().y()))
            title, title_h, text, text_h = plan
            origin = rect.topLeft() + QPointF(16, 16)
            painter.setPen(theme.qcolor("link"))
            title.draw(painter, origin)
            painter.setPen(theme.qcolor("ink"))
            text.draw(painter, origin + QPointF(0, title_h + 12))
            self.text_rects.append(QRectF(origin, QSizeF(rect.width() - 32, title_h + 12 + text_h)))


class RoadmapImageDialog(QDialog):
    """기존 로드맵 그림의 비율과 바이트를 유지하며 확대해 보여 줌."""
    def __init__(self, path, title, parent=None):
        super().__init__(parent)
        kit.page(self)
        self.setWindowTitle(title)
        self.original = QPixmap(str(path))
        self.scale = 1.0
        self._closing = False
        self.shell = DialogLayout(self, title)
        self.area = QScrollArea()
        self.area.setMinimumSize(0, 0)
        self.area.setWidgetResizable(False)
        self.image = QLabel()
        self.image.setAccessibleName(title)
        self.area.setWidget(self.image)
        self.shell.content.addWidget(self.area)
        self.less, self.more, self.fit, self.close_button = (kit.button(text) for text in ("축소", "확대", "폭에 맞추기", "닫기"))
        self.less.clicked.connect(lambda: self.zoom(self.scale / 1.25))
        self.more.clicked.connect(lambda: self.zoom(self.scale * 1.25))
        self.fit.clicked.connect(self.fit_width)
        self.close_button.clicked.connect(self.accept)
        self.shell.actions.set_actions([self.less, self.more, self.fit], [self.close_button])
        self.shell.fit(1024, 800)
        self.zoom(1)

    def showEvent(self, event):
        super().showEvent(event)
        if not self._closing and motion.enabled:
            effect = getattr(self, "_opacity_effect", None)
            if effect is not None:
                effect.setOpacity(0.0)
            motion.fade_opacity(self, True)

    def done(self, result):
        if self._closing:
            return
        self._closing = True
        self.setEnabled(False)

        def finish():
            self.setEnabled(True)
            self._closing = False
            super(RoadmapImageDialog, self).done(result)

        if motion.enabled and self.isVisible():
            motion.fade_opacity(self, False, finish)
        else:
            motion.play(self, 0, lambda _: None, finish)

    def zoom(self, scale):
        if self.original.isNull():
            self.image.setText("로드맵 그림을 읽지 못했습니다.")
            return
        self.scale = min(3, max(0.1, scale))
        pixmap = self.original.scaled(self.original.size() * self.scale, Qt.AspectRatioMode.KeepAspectRatio,
                                      Qt.TransformationMode.SmoothTransformation)
        self.image.setPixmap(pixmap)
        self.image.resize(pixmap.size())

    def fit_width(self):
        if not self.original.isNull():
            self.zoom((self.area.viewport().width() - 16) / self.original.width())


class CareerRoadmapPage(ReadingPage):
    goal_requested = pyqtSignal(str, str)

    def __init__(self, parent=None, *, catalog=None, repository=None, on_back=None, on_select_goal=None,
                 on_video=None, on_magazine=None, on_source=None):
        super().__init__(parent, on_back)
        self.catalog = catalog if catalog is not None else load_catalog()
        self.repository = Path(repository) if repository is not None else Path(__file__).resolve().parents[1]
        self.on_select_goal = on_select_goal
        self.on_source = on_source
        self.selected_role_id = None
        self.saved_role_id = None
        title = kit.para("개발자 로드맵", "title")
        title.setProperty("reading_anchor", True)
        self.body.addWidget(kit.heading(title, kit.para("어떤 제품의 어느 부분을 만들고 싶은지 살펴보세요. 직무를 고르면 하는 일과 학습 순서가 이어집니다.")))
        if on_magazine:
            magazine = kit.button("매거진에서 영상 보기", "text")
            magazine.clicked.connect(on_magazine)
            self.body.addWidget(flow_buttons(magazine))
        self.body.addSpacing(24)
        self.notice = kit.para("직무 설명은 인터넷 없이도 읽을 수 있습니다.", "caption", "secondary")
        self.body.addWidget(self.notice)
        self.add_section("관심 있는 제품과 직무", "관심 산업을 고른 뒤 어떤 제품의 어느 부분을 만들지 좁혀보세요.")
        self.industry, self.product, self.role_picker = (kit.typed(QComboBox(), "body") for _ in range(3))
        groups = []
        for combo, name in ((self.industry, "산업"), (self.product, "제품 예시"), (self.role_picker, "세부 직무")):
            combo.setAccessibleName(name)
            combo.setMinimumHeight(theme.control_height("l"))
            combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            combo.setMinimumContentsLength(1)
            combo.setMinimumWidth(0)
            combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            groups.append(kit.heading(kit.para(name, "body", bold=True), combo))
        self.filters = CareerFilters(groups)
        self.body.addWidget(self.filters)
        self.body.addSpacing(24)
        self.industry.addItem("모든 산업", None)
        for row in self.catalog.industries:
            self.industry.addItem(row["label"], row["id"])
        self.context_flow = CareerFlow()
        self.context_flow.setAccessibleName("산업에서 직무까지")
        self.body.addWidget(self.context_flow)
        self.body.addSpacing(12)
        self.body.addWidget(kit.para(self.catalog.organization_caption, "caption", "secondary"))
        self.body.addSpacing(theme.GAP["detail"])
        self.team_note = kit.para("", "caption", "secondary")
        self.body.addWidget(self.team_note)
        self.add_section("입력에서 산출물까지", "직무별로 받는 자료와 하는 일, 작업이 끝나면 남기는 결과를 예로 보여 줍니다.")
        self.role_title = kit.para("", "headline")
        self.role_title.setProperty("reading_anchor", True)
        self.body.addWidget(self.role_title)
        self.body.addSpacing(24)
        self.work_flow = CareerFlow()
        self.body.addWidget(self.work_flow)
        self.add_section("이 직무와 연결해 배울 내용", "순서는 학습 제안입니다. 수업 포함 표시는 ROKEY 11기 교과 범위이며 실무 역량 충족을 뜻하지 않습니다.")
        self.relation = kit.para("", "body", "secondary")
        self.body.addWidget(self.relation)
        self.body.addSpacing(24)
        self.learning = QWidget()
        self.learning_box = kit.box(self.learning, spacing=16)
        self.body.addWidget(self.learning)
        self.body.addSpacing(24)
        self.image_button = kit.button("연결된 로드맵 크게 보기")
        self.image_button.clicked.connect(self.open_image)
        self.goal_button = kit.button("이 직무를 목표로 선택", "primary")
        self.goal_button.clicked.connect(self.choose_goal)
        self.actions = flow_buttons(self.image_button, self.goal_button)
        self.body.addWidget(self.actions)
        self.goal_button.setVisible(on_select_goal is not None)
        self.image_notice = kit.para("", "caption", "secondary")
        self.body.addWidget(self.image_notice)
        self.add_section("업무를 확인한 공개 출처", "직무 소개와 채용 공고를 나눠 적었습니다. 채용 중인지와 최신 조건은 원문에서 확인하세요.")
        self.source_box = QWidget()
        self.sources_layout = kit.box(self.source_box, spacing=24)
        self.body.addWidget(self.source_box)
        if on_video:
            self.add_section("로봇 커리어 영상", "직무와 준비 방향을 다룬 영상을 매거진에서 엽니다.")
            one, two = kit.button("조직과 업무 살펴보기"), kit.button("작은 프로젝트 준비하기")
            one.clicked.connect(lambda: on_video("H89Az-iZZrc"))
            two.clicked.connect(lambda: on_video("HCx2ICUe0eA"))
            self.body.addWidget(flow_buttons(one, two))
        self.industry.currentIndexChanged.connect(self._industry_changed)
        self.product.currentIndexChanged.connect(self._filter_roles)
        self.role_picker.currentIndexChanged.connect(self._show_role)
        self._industry_changed()
        if self.catalog.states["roles"] != "ready":
            state = self.catalog.states["roles"]
            self.notice.setText("공개한 직무 자료가 아직 없습니다." if state == "empty" else "직무 자료를 읽지 못했습니다. 프로그램을 업데이트한 뒤 다시 열어 주세요.")

    def _industry_changed(self, *_):
        current = self.product.currentData()
        self.product.blockSignals(True)
        self.product.clear()
        self.product.addItem("모든 제품 예시", None)
        industry = self.industry.currentData()
        for row in self.catalog.products:
            if not industry or industry in row["industry_ids"]:
                self.product.addItem(row["label"], row["id"])
        index = self.product.findData(current)
        self.product.setCurrentIndex(max(0, index))
        self.product.blockSignals(False)
        self._filter_roles()

    def _filter_roles(self, *_):
        current = self.selected_role_id
        self.role_picker.blockSignals(True)
        self.role_picker.clear()
        for row in self.catalog.roles_for(self.industry.currentData(), self.product.currentData()):
            self.role_picker.addItem(row["title"], row["id"])
            self.role_picker.setItemData(self.role_picker.count() - 1, row["title"], Qt.ItemDataRole.ToolTipRole)
        self.role_picker.setCurrentIndex(max(0, self.role_picker.findData(current)) if self.role_picker.count() else -1)
        self.role_picker.blockSignals(False)
        self._show_role()

    def select_role(self, role_id):
        """목표를 저장하지 않고 지정한 직무를 보여 줌."""
        if self.catalog.role(role_id) is None:
            return False
        self.selected_role_id = role_id
        self.industry.setCurrentIndex(0)
        self.product.setCurrentIndex(0)
        self._filter_roles()
        return True

    def _show_role(self, *_):
        self._anchor = None
        self.selected_role_id = self.role_picker.currentData()
        role = self.catalog.role(self.selected_role_id)
        clear_layout(self.learning_box)
        clear_layout(self.sources_layout)
        self.image_notice.setText("")
        self.image_button.setEnabled(bool(role and role["goal_links"]))
        self.goal_button.setEnabled(role is not None)
        if self.on_select_goal:
            self.goal_button.setText("저장한 관심 직무" if self.saved_role_id == self.selected_role_id else "관심 직무로 저장")
        if role is None:
            self.role_title.setText("조건에 맞는 직무가 없습니다.")
            self.context_flow.set_nodes(())
            self.work_flow.set_nodes(())
            self.team_note.setText("")
            self.relation.setText("산업이나 제품을 바꿔 보세요.")
            return
        industry_id = self.industry.currentData()
        candidates = [item for item in self.catalog.products if item["id"] in role["product_ids"]
                      and (not industry_id or industry_id in item["industry_ids"])]
        product_row = next((item for item in candidates if item["id"] == self.product.currentData()), candidates[0])
        industry_id = industry_id or next(key for key in role["industry_ids"] if key in product_row["industry_ids"])
        industry = next(item["label"] for item in self.catalog.industries if item["id"] == industry_id)
        product = product_row["label"]
        self.context_flow.set_nodes((("산업", industry), ("제품 예시", product), ("부서·팀 사례", role["team_label"]), ("세부 직무", role["title"])))
        self.team_note.setText(role["team_note"])
        self.role_title.setText(role["title"])
        self.work_flow.set_nodes((("받는 입력", "\n".join(role["inputs"])),
                                  ("하는 일", "\n".join(role["tasks"])),
                                  ("남길 산출물", "\n".join(role["outputs"]))))
        link = role["goal_links"][0] if role["goal_links"] else None
        goal = self.catalog.goal(link["goal_id"]) if link else None
        self.relation.setText(f"{RELATION_LABELS[link['relation']]} · {goal['title']}" if goal else "연결한 기존 로드맵이 없습니다.")
        for node in role["roadmap_nodes"]:
            row, box = kit.well(pad_x=16, pad_y=16, spacing=8)
            title = kit.para(node["label"], "body", bold=True)
            title.setProperty("reading_anchor", True)
            box.addWidget(title)
            box.addWidget(kit.para(COURSE_LABELS[node["course_status"]], "caption", "secondary"))
            self.learning_box.addWidget(row)
        for source in self.catalog.sources:
            if source["id"] not in role["source_ids"]:
                continue
            box = QWidget()
            items = kit.box(box, spacing=12)
            items.addWidget(kit.para(source["title"], "body", bold=True))
            items.addWidget(kit.para(f"게시일 {source['published_date'] or '미확인'} · 확인일 {source['checked_date']}", "caption", "secondary"))
            items.addWidget(kit.para(source["summary"]))
            if self.on_source:
                original = kit.button("공개 원문 열기", "text")
                original.setToolTip(source["url"])
                original.clicked.connect(lambda checked=False, url=source["url"]: self.on_source(url))
                items.addWidget(flow_buttons(original))
            self.sources_layout.addWidget(box)

    def choose_goal(self):
        role = self.catalog.role(self.selected_role_id)
        if role:
            goal_id = role["goal_links"][0]["goal_id"] if role["goal_links"] else ""
            if self.on_select_goal:
                self.on_select_goal(role["id"], goal_id)
            self.goal_requested.emit(role["id"], goal_id)

    def set_saved_role(self, role_id):
        self.saved_role_id = role_id
        self.goal_button.setText("저장한 관심 직무" if role_id == self.selected_role_id else "관심 직무로 저장")

    def open_image(self):
        role = self.catalog.role(self.selected_role_id)
        if not role or not role["goal_links"]:
            return
        goal_id = role["goal_links"][0]["goal_id"]
        path = self.repository / "docs" / "roadmap" / f"{goal_id}.png"
        if QPixmap(str(path)).isNull():
            self.image_notice.setText("로드맵 그림을 읽지 못했습니다. 위의 학습 순서와 수업 범위를 확인하세요.")
            return
        self.image_dialog = RoadmapImageDialog(path, self.catalog.goal(goal_id)["title"], self)
        self.image_dialog.open()


RoadmapPage = CareerRoadmapPage
