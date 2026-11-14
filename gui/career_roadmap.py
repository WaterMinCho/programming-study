"""직무를 탐색하고 선택 의도만 콜백으로 전달함. 개인 기록은 쓰지 않음."""
import math
from pathlib import Path

from PyQt6.QtCore import QEvent, QPoint, QPointF, QRectF, QSize, QSizeF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QPainter, QPen, QPixmap, QTextLayout, QTextOption
from PyQt6.QtWidgets import QBoxLayout, QComboBox, QGridLayout, QSizePolicy, QWidget

from career.catalog import RELATION_LABELS, load_catalog
from gui import kit, theme
from gui.career_learning_path import CareerLearningPath
from gui.career_map_viewer import RoadmapImageDialog
from gui.career_scene import RoleScene
from gui.career_role_gallery import RoleGallery


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
    """산업·제품 선택란을 가용 폭에 따라 한 줄 또는 두 줄로 배치함."""
    def __init__(self, groups):
        super().__init__()
        self.groups = groups
        self.pickers = [group.description for group in groups]
        self.wide = None
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(24)
        self._place()

    def _place(self):
        widths = [max((combo.fontMetrics().horizontalAdvance(combo.itemText(i)) for i in range(combo.count())),
                      default=0) for combo in self.pickers]
        wide = self.width() >= 2 * (max(widths) + theme.control_height("l")) + self.grid.spacing()
        if self.wide == wide:
            return
        self.wide = wide
        for group in self.groups:
            self.grid.removeWidget(group)
        self.grid.addWidget(self.groups[0], 0, 0)
        self.grid.addWidget(self.groups[1], 0 if wide else 1, 1 if wide else 0)
        self.grid.setColumnStretch(0, 1)
        self.grid.setColumnStretch(1, 1 if wide else 0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._place()

    def refont(self):
        self._place()


class RoleHeading(QWidget):
    def __init__(self, title, action):
        super().__init__()
        self.title, self.action = title, action
        self.row = kit.box(self, spacing=theme.GAP["group"], horizontal=True)
        self.row.addWidget(title, 1)
        self.row.addWidget(action)

    def refont(self):
        needed = self.title.fontMetrics().horizontalAdvance(self.title.text())
        needed += self.action.sizeHint().width() + self.row.spacing()
        self.row.setDirection(QBoxLayout.Direction.LeftToRight if self.width() >= needed
                              else QBoxLayout.Direction.TopToBottom)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.refont()


class ReadingPage(QWidget):
    """화면 설정과 왕복 때 현재 문단의 화면 위치를 보관함."""
    def __init__(self, parent=None, on_back=None, back_label="← 학습 현황"):
        super().__init__(parent)
        kit.page(self)
        self.setObjectName("page")
        self._anchor = None
        self._settling = False
        self._signature = None
        self._passes = 0
        outer = kit.box(self)
        self.top = kit.TopBar(back_label, plain=True)
        self.top.row.addStretch(1)
        outer.addWidget(self.top)
        self.top.setVisible(on_back is not None)
        self.top.back.setVisible(on_back is not None)
        if on_back:
            self.top.back.clicked.connect(on_back)
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


class CareerRoadmapPage(ReadingPage):
    goal_requested = pyqtSignal(str, str)

    def __init__(self, parent=None, *, catalog=None, repository=None, on_back=None, on_select_goal=None,
                 on_video=None, on_magazine=None, on_source=None):
        super().__init__(parent, on_back)
        self._on_back = on_back
        if on_back:
            self.top.back.clicked.disconnect(on_back)
            self.top.back.clicked.connect(lambda: on_back() if self.browsing else self.show_catalog())
        self.catalog = catalog if catalog is not None else load_catalog()
        self.image_dialog = None
        self.repository = Path(repository) if repository is not None else Path(__file__).resolve().parents[1]
        self.on_select_goal = on_select_goal
        self.on_source = on_source
        self.selected_role_id = None
        self.saved_role_id = None
        self.browsing = True
        self._catalog_anchor = None
        self._detail_anchors = {}
        self._detail_index = 0
        self.intro = QWidget()
        intro = kit.box(self.intro, spacing=theme.GAP["title_description"])
        title = kit.para("개발자 로드맵", "title")
        title.setProperty("reading_anchor", True)
        intro.addWidget(title)
        intro.addWidget(kit.para("관심 있는 직무를 고르세요. 하는 일과 준비할 기술을 그림으로 확인할 수 있습니다.", "body", "secondary"))
        self.body.addWidget(self.intro)
        self.catalog_gap = QWidget()
        self.catalog_gap.setFixedHeight(theme.GAP["paragraph"])
        self.body.addWidget(self.catalog_gap)
        self.industry, self.product, self.role_picker = (kit.typed(QComboBox(), "body") for _ in range(3))
        for combo, name in ((self.industry, "산업"), (self.product, "제품 예시"), (self.role_picker, "세부 직무")):
            combo.setAccessibleName(name)
            combo.setMinimumHeight(theme.control_height("l"))
            combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            combo.setMinimumContentsLength(1)
            combo.setMinimumWidth(0)
            combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        controls = self.controls = QWidget()
        select = kit.box(controls, spacing=theme.GAP["detail"], horizontal=True)
        self.catalog_button = kit.button("직무 목록", "secondary", "l")
        self.catalog_button.clicked.connect(self.show_catalog)
        select.addWidget(self.catalog_button)
        select.addWidget(self.role_picker, 1)
        self.catalog_count = kit.para("", "label", "secondary")
        select.addWidget(self.catalog_count, 1)
        self.filter_toggle = kit.button("산업·제품 필터", "secondary", "l")
        self.filter_toggle.setCheckable(True)
        self.filter_toggle.setToolTip("산업과 제품으로 직무 좁히기")
        select.addWidget(self.filter_toggle)
        self.body.addWidget(controls)
        self.filters = CareerFilters([kit.heading(kit.para(name, "label"), combo)
                                     for name, combo in (("산업", self.industry), ("제품 예시", self.product))])
        self.filters.grid.setContentsMargins(0, theme.GAP["paragraph"], 0, 0)
        self.body.addWidget(self.filters)
        self.filters.hide()
        self.filter_toggle.toggled.connect(self._toggle_filters)
        self.controls_gap = QWidget()
        self.controls_gap.setFixedHeight(theme.GAP["paragraph"])
        self.body.addWidget(self.controls_gap)
        self.industry.addItem("모든 산업", None)
        for row in self.catalog.industries:
            self.industry.addItem(row["label"], row["id"])
        self.notice = kit.para("", "body", "secondary")
        self.body.addWidget(self.notice)
        self.gallery = RoleGallery()
        self.gallery.picked.connect(self._open_catalog_role)
        self.body.addWidget(self.gallery)
        self.details = QWidget()
        self.body.addWidget(self.details)
        details = kit.box(self.details)
        self.role_title = kit.para("", "title")
        self.role_title.setProperty("reading_anchor", True)
        self.goal_button = kit.button("관심 직무로 저장")
        self.goal_button.clicked.connect(self.choose_goal)
        self.role_heading = RoleHeading(self.role_title, self.goal_button)
        self.goal_button.setVisible(on_select_goal is not None)
        details.addWidget(self.role_heading)
        details.addSpacing(theme.GAP["description_content"])
        self.detail_tabs = kit.TabBar(("업무·결과", "학습 로드맵"))
        details.addWidget(self.detail_tabs)
        details.addSpacing(theme.GAP["description_content"])
        self.work_panel, self.path_panel = QWidget(), QWidget()
        self.work_panel.setProperty("reading_anchor", True)
        details.addWidget(self.work_panel)
        details.addWidget(self.path_panel)
        self.path_panel.hide()
        work = kit.box(self.work_panel)
        path = kit.box(self.path_panel)
        self.detail_tabs.picked.connect(self.show_detail_tab)
        self.image_button = kit.button("학습 로드맵 크게 보기", "primary")
        self.image_button.clicked.connect(self.open_image)
        self.scene = RoleScene()
        work.addWidget(self.scene)
        self.image_notice = kit.para("", "caption", "secondary")
        self.image_notice.hide()
        work.addSpacing(theme.GAP["section"])
        self.team_toggle = kit.button("팀과 담당 업무 펼치기")
        self.team_toggle.setCheckable(True)
        self.team_toggle.setProperty("reading_anchor", True)
        work.addWidget(self.team_toggle, 0, Qt.AlignmentFlag.AlignLeft)
        team_details = QWidget()
        team_box = kit.box(team_details, margins=(0, theme.GAP["paragraph"], 0, 0))
        work.addWidget(team_details)
        team_details.hide()
        self.team_toggle.toggled.connect(team_details.setVisible)
        self.team_toggle.toggled.connect(lambda opened: self.team_toggle.setText(
            "팀과 담당 업무 접기" if opened else "팀과 담당 업무 펼치기"))
        self.context_flow = CareerFlow()
        self.context_flow.setAccessibleName("제품과 담당 조직 사례")
        team_box.addWidget(self.context_flow)
        team_box.addSpacing(theme.GAP["detail"])
        self.team_note = kit.para("", "caption", "secondary")
        team_box.addWidget(self.team_note)
        team_box.addSpacing(theme.GAP["description_content"])
        self.work_flow = CareerFlow()
        team_box.addWidget(self.work_flow)
        learn_title = kit.para("ROKEY 11기 수업 범위와 추천 순서", "caption", "secondary")
        learn_title.setProperty("reading_anchor", True)
        path.addWidget(flow_buttons(self.image_button))
        path.addWidget(self.image_notice)
        path.addSpacing(theme.GAP["detail"])
        self.relation = kit.para("", "caption", "secondary")
        self.relation.setProperty("reading_anchor", True)
        path.addWidget(self.relation)
        path.addSpacing(theme.GAP["description_content"])
        path.addWidget(learn_title)
        path.addSpacing(theme.GAP["detail"])
        self.learning, self.learning_box = kit.well(pad_x=16, pad_y=16, spacing=16)
        path.addWidget(self.learning)
        work.addSpacing(theme.GAP["section"])
        self.sources_button = kit.button("직무 소개와 채용 공고 펼치기")
        self.sources_button.setCheckable(True)
        self.sources_button.setProperty("reading_anchor", True)
        work.addWidget(self.sources_button, 0, Qt.AlignmentFlag.AlignLeft)
        self.source_box = QWidget()
        self.sources_layout = kit.box(self.source_box, margins=(0, theme.GAP["group"], 0, 0), spacing=24)
        work.addWidget(self.source_box)
        self.source_box.hide()
        self.sources_button.toggled.connect(self._toggle_sources)
        if on_video or on_magazine:
            work.addSpacing(theme.GAP["section"])
            videos_title = kit.para("관련 영상", "headline")
            videos_title.setProperty("reading_anchor", True)
            work.addWidget(videos_title)
            links = []
            if on_video:
                for label, video_id in (("로봇 개발자의 업무", "H89Az-iZZrc"), ("로봇 개발 프로젝트 준비", "HCx2ICUe0eA")):
                    link = kit.button(label)
                    link.clicked.connect(lambda checked=False, key=video_id: on_video(key))
                    links.append(link)
            if on_magazine:
                magazine = kit.button("매거진 열기", "text")
                magazine.clicked.connect(on_magazine)
                links.append(magazine)
            work.addWidget(flow_buttons(*links))
        self.industry.currentIndexChanged.connect(self._industry_changed)
        self.product.currentIndexChanged.connect(self._filter_roles)
        self.role_picker.currentIndexChanged.connect(self._pick_role)
        self._industry_changed()

    def _reset_reading(self):
        self._timer.stop()
        self._settling = False
        self._anchor = None

    def _show_mode(self):
        has_role = self.catalog.role(self.selected_role_id) is not None
        self.intro.setVisible(self.browsing)
        self.catalog_gap.setVisible(self.browsing)
        self.gallery.setVisible(self.browsing)
        self.catalog_count.setVisible(self.browsing)
        self.role_picker.hide()
        self.filter_toggle.setVisible(self.browsing)
        self.filters.setVisible(self.browsing and self.filter_toggle.isChecked())
        self.controls.setVisible(self.browsing or self._on_back is None)
        self.controls_gap.setVisible(self.browsing or self._on_back is None)
        self.catalog_button.setVisible(not self.browsing)
        self.top.back.setText("← 학습 현황" if self.browsing else "← 직무 목록")
        self.details.setVisible(not self.browsing and has_role)

    def show_catalog(self):
        self._reset_reading()
        self.browsing = True
        self._show_mode()
        self._anchor = self._catalog_anchor
        self._schedule_restore()
        card = self.gallery.cards.get(self.selected_role_id)
        if card is not None and self._catalog_anchor is not None:
            card.setFocus(Qt.FocusReason.OtherFocusReason)

    def _open_catalog_role(self, role_id):
        index = self.role_picker.findData(role_id)
        if index < 0:
            return
        self._remember()
        self._catalog_anchor = self._anchor
        self.role_picker.blockSignals(True)
        self.role_picker.setCurrentIndex(index)
        self.role_picker.blockSignals(False)
        self._pick_role()
        self.show_detail_tab(0)

    def _pick_role(self, *_):
        self._reset_reading()
        self._detail_anchors.clear()
        self.browsing = False
        self._show_role()
        self.scroll.verticalScrollBar().setValue(0)
        (self.top.back if self._on_back else self.catalog_button).setFocus(Qt.FocusReason.OtherFocusReason)

    def show_detail_tab(self, index):
        if index == self._detail_index:
            return
        self._remember()
        self._detail_anchors[self._detail_index] = self._anchor
        self._reset_reading()
        self._detail_index = index
        self.detail_tabs.set_current(index)
        self.work_panel.setVisible(index == 0)
        self.path_panel.setVisible(index == 1)
        self.scroll.verticalScrollBar().setValue(0)
        self._anchor = self._detail_anchors.get(index)
        self._schedule_restore()

    def _toggle_filters(self, opened):
        top = self.controls.mapTo(self.scroll.viewport(), QPoint()).y()
        self._anchor = self.controls, top
        self.filters.setVisible(opened)

    def _toggle_sources(self, opened):
        self.source_box.setVisible(opened)
        self.sources_button.setText("직무 소개와 채용 공고 접기" if opened else "직무 소개와 채용 공고 펼치기")

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
        self.filters.refont()
        self._filter_roles()

    def _filter_roles(self, *_):
        current = self.selected_role_id
        self.role_picker.blockSignals(True)
        self.role_picker.clear()
        roles = self.catalog.roles_for(self.industry.currentData(), self.product.currentData())
        for row in roles:
            self.role_picker.addItem(row["title"], row["id"])
            self.role_picker.setItemData(self.role_picker.count() - 1, row["title"], Qt.ItemDataRole.ToolTipRole)
        self.role_picker.setCurrentIndex(max(0, self.role_picker.findData(current)) if self.role_picker.count() else -1)
        self.role_picker.blockSignals(False)
        self.gallery.set_roles(roles)
        self.gallery.set_saved(self.saved_role_id)
        self.gallery.set_selected(self.selected_role_id)
        self.catalog_count.setText(f"직무 {len(roles)}개")
        active = any(combo.currentData() is not None for combo in (self.industry, self.product))
        self.filter_toggle.setText("산업·제품 필터 적용 중" if active else "산업·제품 필터")
        self.notice.setVisible(not roles)
        if not roles:
            state = self.catalog.states["roles"]
            if state == "ready":
                self.filter_toggle.setChecked(True)
                self.notice.setText("조건에 맞는 직무가 없습니다. 산업이나 제품을 바꿔 보세요.")
            elif state == "empty":
                self.notice.setText("공개한 직무 자료가 아직 없습니다.")
            else:
                self.notice.setText("직무 자료를 읽지 못했습니다. 프로그램을 업데이트한 뒤 다시 열어 주세요.")
        self._show_mode()

    def select_role(self, role_id):
        """목표를 저장하지 않고 지정한 직무를 보여 줌."""
        if self.catalog.role(role_id) is None:
            return False
        self.selected_role_id = role_id
        self.industry.blockSignals(True)
        self.industry.setCurrentIndex(0)
        self.industry.blockSignals(False)
        self.product.blockSignals(True)
        self.product.setCurrentIndex(0)
        self.product.blockSignals(False)
        self._industry_changed()
        self._pick_role()
        return True

    def _show_role(self, *_):
        self._anchor = None
        self.selected_role_id = self.role_picker.currentData()
        role = self.catalog.role(self.selected_role_id)
        clear_layout(self.learning_box)
        clear_layout(self.sources_layout)
        self.image_notice.setText("")
        self.image_notice.hide()
        self.image_button.setEnabled(bool(role and role["goal_links"]))
        self.goal_button.setEnabled(role is not None)
        if self.on_select_goal:
            self.goal_button.setText("저장한 관심 직무" if self.saved_role_id == self.selected_role_id else "관심 직무로 저장")
        self._show_mode()
        self.notice.hide()
        if role is None:
            return
        self.role_title.setText(role["title"])
        self.role_heading.refont()
        self.gallery.set_selected(self.selected_role_id)
        self.scene.set_role(role)
        industry_id = self.industry.currentData()
        candidates = [item for item in self.catalog.products if item["id"] in role["product_ids"]
                      and (not industry_id or industry_id in item["industry_ids"])]
        product_row = next((item for item in candidates if item["id"] == self.product.currentData()), candidates[0])
        industry_id = industry_id or next(key for key in role["industry_ids"] if key in product_row["industry_ids"])
        industry = next(item["label"] for item in self.catalog.industries if item["id"] == industry_id)
        product = product_row["label"]
        self.context_flow.set_nodes((("제품 예시", f"{industry} · {product}"), ("조직·업무 분류 사례", role["team_label"])))
        self.team_note.setText(role["team_note"] + " 회사마다 조직 이름과 업무 범위가 다릅니다.")
        self.work_flow.set_nodes((
            ("입력 예시", "\n".join(role["inputs"])),
            ("하는 일", "\n".join(role["tasks"])),
            ("산출물 예시", "\n".join(role["outputs"])),
        ))
        link = role["goal_links"][0] if role["goal_links"] else None
        goal = self.catalog.goal(link["goal_id"]) if link else None
        self.relation.setText(f"{RELATION_LABELS[link['relation']]} · {goal['title']}" if goal else "연결한 기존 로드맵이 없습니다.")
        self.learning_path = CareerLearningPath(role["roadmap_nodes"], role["outputs"])
        self.learning_box.addWidget(self.learning_path)
        for source in self.catalog.sources:
            if source["id"] not in role["source_ids"]:
                continue
            box = QWidget()
            box.setProperty("reading_anchor", True)
            items = kit.box(box, spacing=12)
            items.addWidget(kit.para(source["title"], "body", bold=True))
            items.addWidget(kit.para(f"게시일 {source['published_date'] or '미확인'} · 확인일 {source['checked_date']}", "caption", "secondary"))
            items.addWidget(kit.para(source["summary"]))
            if self.on_source:
                label = {"employer_job": "채용 공고 열기", "employer_team_catalog": "팀 소개 열기",
                         "employer_role_catalog": "직무 소개 열기"}.get(source.get("kind"), "원문 열기")
                original = kit.button(label, "text")
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
        self.gallery.set_saved(role_id)
        self.goal_button.setText("저장한 관심 직무" if role_id == self.selected_role_id else "관심 직무로 저장")

    def open_image(self):
        role = self.catalog.role(self.selected_role_id)
        if not role or not role["goal_links"]:
            return
        self.show_detail_tab(1)
        goal_id = role["goal_links"][0]["goal_id"]
        path = self.repository / "docs" / "roadmap" / f"{goal_id}.png"
        if self.image_dialog is not None:
            self.image_dialog.raise_()
            self.image_dialog.activateWindow()
            return
        original = QPixmap(str(path))
        if original.isNull():
            self.image_notice.show()
            self.image_notice.setText("로드맵 그림을 읽지 못했습니다. 아래 추천 학습 순서를 확인하세요.")
            return
        self.image_notice.setText("")
        self.image_notice.hide()
        dialog = RoadmapImageDialog(original, self.catalog.goal(goal_id)["title"], self)
        self.image_dialog = dialog
        dialog.finished.connect(self._image_closed)
        dialog.finished.connect(dialog.deleteLater)
        dialog.showMaximized()

    def _image_closed(self):
        self.image_dialog = None
        self.image_button.setFocus(Qt.FocusReason.OtherFocusReason)


RoadmapPage = CareerRoadmapPage
