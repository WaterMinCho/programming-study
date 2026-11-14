"""원래 추천 순서와 수업 범위, 그림 설명과 작은 창의 배치를 확인함."""
from copy import deepcopy
import json
from pathlib import Path
import os
import unittest
from unittest.mock import Mock

from tests import guikit
from PyQt6.QtCore import QPoint, QRectF
from PyQt6.QtGui import QFontMetricsF
from PyQt6.QtWidgets import QLabel

from career.catalog import COURSE_LABELS, load_catalog
from gui import kit, theme
from gui.career_learning_path import CareerLearningPath, EXAMPLES
from gui.career_roadmap import CareerRoadmapPage


class CareerLearningPathTest(unittest.TestCase):
    def setUp(self):
        self.catalog = load_catalog()
        self.windows = []
        self.appearance = dict(theme.state)

    def tearDown(self):
        for window in self.windows:
            window.close()
            window.deleteLater()
        guikit.pump(1)
        theme.set_text(self.appearance["text"])
        theme.set_mode(self.appearance["mode"])

    def path(self, role_id="robot_policy"):
        role = self.catalog.role(role_id)
        widget = CareerLearningPath(role["roadmap_nodes"], role["outputs"])
        kit.page(widget)
        self.windows.append(widget)
        widget.show()
        return widget

    def resize_path(self, path, width):
        kit.refont(path)
        path.resize(width, path.heightForWidth(width))
        guikit.pump(1)
        path.grab()

    def settle(self, page):
        previous, stable = None, 0
        for _ in range(60):
            guikit.pump(5)
            path = page.learning_path
            current = (page.content.size(), path.size(), tuple(step.geometry() for step in path.steps),
                       page.scroll.verticalScrollBar().maximum())
            stable = stable + 1 if current == previous else 0
            previous = current
            if stable >= 3 and not page._settling:
                return
        self.fail("화면 배치가 안정되지 않았음")

    def test_catalog_order_labels_course_scope_and_outputs_stay_unchanged(self):
        before = deepcopy(self.catalog.roles)
        callback = Mock()
        page = CareerRoadmapPage(catalog=self.catalog, on_select_goal=callback)
        self.windows.append(page)
        for role in self.catalog.roles:
            page.select_role(role["id"])
            path = page.learning_path
            self.assertEqual(path.nodes, tuple(role["roadmap_nodes"]))
            self.assertEqual(path.outputs, tuple(role["outputs"]))
            self.assertIs(page.learning_box.itemAt(0).widget(), path)
            labels = [label.text() for label in page.learning.findChildren(QLabel) if not label.isHidden()]
            for i, (step, node) in enumerate(zip(path.steps, role["roadmap_nodes"]), 1):
                self.assertEqual(step.title.text(), f"{i}. {node['label']}")
                self.assertEqual(step.status.text(), COURSE_LABELS[node["course_status"]])
                self.assertIn(step.title.text(), labels)
                self.assertIn(step.status.text(), labels)
            self.assertIn("\n".join(role["outputs"]), path.output.text())
        callback.assert_not_called()
        self.assertEqual(before, self.catalog.roles)

    def test_each_published_subject_has_an_input_and_change_example(self):
        kinds = set()
        for role in self.catalog.roles:
            path = self.path(role["id"])
            for step in path.steps:
                label = step.node["label"]
                self.assertIn(label, EXAMPLES)
                kind, caption = EXAMPLES[label]
                kinds.add(kind)
                self.assertEqual(step.example.kind, kind)
                self.assertEqual(step.caption.text(), caption)
                self.assertEqual(step.example.accessibleDescription(), f"{label}. {caption}")
                self.assertIn("수업 범위", path.accessibleDescription())
                self.assertNotIn("완료", step.status.text())
        self.assertTrue({"axes", "matrix", "nodes", "response", "image", "curve"}.issubset(kinds))

    def test_maximum_font_all_roles_keep_text_and_figures_inside_both_themes(self):
        theme.set_text("larger")
        for mode in ("light", "dark"):
            theme.set_mode(mode)
            for role in self.catalog.roles:
                path = self.path(role["id"])
                for width in (320, 656, 1184):
                    with self.subTest(mode=mode, role=role["id"], width=width):
                        self.resize_path(path, width)
                        self.assertEqual(path.sizePolicy().hasHeightForWidth(), True)
                        self.assertEqual(path.height(), path.heightForWidth(width))
                        for step in path.steps:
                            self.assertTrue(path.rect().contains(step.geometry()))
                            self.assertEqual(step.title.y(), step.status.y())
                            self.assertGreaterEqual(step.status.width(), QFontMetricsF(step.status.font()).horizontalAdvance(step.status.text()))
                            self.assertLessEqual(step.title.geometry().right(), step.status.x() - theme.GAP["title_description"])
                            for text in (step.title, step.status, step.caption):
                                self.assertGreaterEqual(text.height(), text.heightForWidth(text.width()))
                                self.assertTrue(step.rect().contains(text.geometry()))
                            self.assertTrue(step.rect().contains(step.example.geometry()))
                        self.assertTrue(path.rect().contains(path.output.geometry()))
                        self.assertEqual(len({(step.example.height(), step.width()) for step in path.steps}), 1)

    def test_column_threshold_uses_current_font_and_reverses_after_resize(self):
        path = self.path()
        for text, width, expected in (("normal", 1100, 3), ("larger", 1100, 2),
                                      ("larger", 656, 1), ("normal", 1100, 3)):
            theme.set_text(text)
            self.resize_path(path, width)
            self.assertEqual(path.columns, expected, (text, width))
            rects = [step.geometry() for step in path.steps]
            for i, rect in enumerate(rects):
                if i % expected:
                    self.assertEqual(rect.top(), rects[i - 1].top())
                    self.assertGreater(rect.left(), rects[i - 1].right())
                elif i:
                    self.assertGreater(rect.top(), rects[i - 1].bottom())

    def test_robot_links_and_reward_are_distinct_from_nodes_and_loss(self):
        path = self.path()
        by_label = {step.node["label"]: step for step in path.steps}
        robot = by_label["ROS2와 로봇 모델"]
        reward = by_label["강화학습 기초"]
        self.assertEqual(robot.example.kind, "robot")
        self.assertIn("링크", robot.caption.text())
        self.assertIn("관절", robot.caption.text())
        self.assertIn("ROS 실행 노드와 구분", robot.caption.text())
        self.assertEqual(reward.example.kind, "reward")
        self.assertIn("가로축은 반복", reward.caption.text())
        self.assertIn("세로축은 환경에서 얻은 보상", reward.caption.text())
        self.assertNotEqual(reward.example.kind, EXAMPLES["학습 튜닝"][0])

    def example(self, role_id, label):
        path = self.path(role_id)
        self.resize_path(path, 320)
        return next(step.example for step in path.steps if step.node["label"] == label)

    def figure_ink(self, widget, x, y, tone, offset=(0, 0)):
        image = widget.grab().toImage()
        ratio = image.devicePixelRatioF()
        cx = round((8 + (widget.width() - 16) * x / 100 + offset[0]) * ratio)
        cy = round((8 + (widget.height() - 16) * y / 100 + offset[1]) * ratio)
        radius = max(1, round(ratio))
        return any(guikit.near(image.pixelColor(px, py), tone)
                   for px in range(max(0, cx - radius), min(image.width(), cx + radius + 1))
                   for py in range(max(0, cy - radius), min(image.height(), cy + radius + 1)))

    def test_failure_examples_draw_blocked_route_missing_message_and_process_stop(self):
        theme.set_text("larger")
        for mode in ("light", "dark"):
            theme.set_mode(mode)
            recovery = self.example("robot_navigation", "주행 실패 복구")
            route = self.example("robot_navigation", "Nav2")
            messages = self.example("robot_backend", "실시간 통신")
            process = self.example("field_integration", "Linux 운영")
            self.assertTrue(self.figure_ink(recovery, 48, 65, "wrong"))
            self.assertFalse(self.figure_ink(route, 48, 65, "wrong"))
            self.assertTrue(self.figure_ink(recovery, 32, 22, "link"))
            self.assertTrue(self.figure_ink(messages, 39, 66, "link"))
            self.assertTrue(self.figure_ink(messages, 72, 66, "link"))
            self.assertTrue(self.figure_ink(messages, 91, 66, "wrong"))
            self.assertFalse(self.figure_ink(messages, 91, 66, "link"))
            self.assertTrue(self.figure_ink(process, 55, 40, "wrong"))

    def test_transfer_arrows_draw_both_wings_and_response_returns_to_input(self):
        theme.set_text("larger")
        for mode in ("light", "dark"):
            theme.set_mode(mode)
            cases = (("robot_control", "ROS2 기본", 39, 30),
                     ("robot_backend", "백엔드 API", 38, 35),
                     ("robot_vision", "이미지 분류 모델", 70, 50),
                     ("backend", "SQL과 DB", 74, 50),
                     ("robot_control", "C++ 실전", 38, 35))
            for role, label, x, y in cases:
                with self.subTest(mode=mode, label=label):
                    example = self.example(role, label)
                    for offset in ((-5, -3), (-5, 3)):
                        self.assertTrue(self.figure_ink(example, x, y, "link", offset))
            request = self.example("robot_backend", "백엔드 API")
            for offset in ((-3, 5), (3, 5)):
                self.assertTrue(self.figure_ink(request, 14, 78, "muted", offset))

    def test_chart_legends_and_coordinate_sides_are_explicit_in_descriptions(self):
        expected = {
            "좌표계와 변환": ("왼쪽", "센서 좌표", "오른쪽", "로봇 좌표"),
            "좌표 변환": ("왼쪽 센서 좌표", "오른쪽 로봇 좌표"),
            "학습 튜닝": ("가로축", "학습 반복", "세로축", "손실", "파란 실선", "학습 손실", "회색 점선", "검증 손실"),
            "ros2_control": ("가로축은 시간", "세로축은 위치", "회색 점선", "목표 위치", "파란 실선", "장치 응답"),
            "센서 데이터": ("가로축은 시간", "세로축은 센서 값"),
        }
        for role in self.catalog.roles:
            path = self.path(role["id"])
            for step in path.steps:
                for text in expected.get(step.node["label"], ()):
                    self.assertIn(text, step.caption.text())
                    self.assertIn(text, step.example.accessibleDescription())

    def test_message_labels_fit_and_time_is_below_the_axis(self):
        theme.set_text("larger")
        for mode in ("light", "dark"):
            theme.set_mode(mode)
            example = self.example("robot_backend", "실시간 통신")
            example.grab()
            labels = dict(example.label_bounds)
            self.assertEqual(set(labels), {"송신", "수신", "1", "2", "3", "시간"})
            for bounds in labels.values():
                self.assertTrue(QRectF(example.rect()).contains(bounds))
            axis_y = 8 + (example.height() - 16) * .80
            self.assertGreater(labels["시간"].top(), axis_y + 1)

    def test_page_maximum_font_all_roles_keep_text_and_fit_work_area(self):
        page = CareerRoadmapPage(catalog=self.catalog)
        page.select_role("robot_control")
        page.show_detail_tab(1)
        self.windows.append(page)
        self.capture_widget = page
        page.resize(760, 480)
        page.show()
        self.settle(page)
        native = guikit.APP.platformName() != "offscreen"
        room = page.screen().availableGeometry()
        frame_width = page.frameGeometry().width() - page.width()
        frame_height = page.frameGeometry().height() - page.height()
        if native and (room.width() < 760 + frame_width or room.height() < 480 + frame_height):
            self.skipTest("실제 작업 영역에서 760×480 창과 프레임을 표시하지 못함")
        records = []
        theme.set_text("larger")
        for mode in ("light", "dark"):
            theme.set_mode(mode)
            kit.refont(page)
            for requested_width, requested_height in ((760, 480), (1024, 700), (1280, 800)):
                width, height = requested_width, requested_height
                if native and requested_width > 760:
                    width = min(width, room.width() - frame_width - 32)
                    height = min(height, room.height() - frame_height - 32)
                page.resize(width, height)
                if native:
                    page.move(room.topLeft() + QPoint(16, 16))
                self.settle(page)
                if native:
                    # 창 장식 위치를 실제 프레임으로 다시 대조함.
                    frame = page.frameGeometry()
                    dx = max(room.left() - frame.left(), 0) + min(room.right() - frame.right(), 0)
                    dy = max(room.top() - frame.top(), 0) + min(room.bottom() - frame.bottom(), 0)
                    page.move(page.pos() + QPoint(dx, dy))
                    self.settle(page)
                    self.assertTrue(room.contains(page.frameGeometry()))
                self.assertEqual((page.width(), page.height()), (width, height))
                if requested_width == 760:
                    self.assertEqual((page.width(), page.height()), (760, 480))
                records.append({"mode": mode, "requested": [requested_width, requested_height],
                                "actual": [page.width(), page.height()],
                                "frame": page.frameGeometry().getRect(), "available": room.getRect(),
                                "platform": guikit.APP.platformName(), "scale": page.devicePixelRatioF()})
                for role in self.catalog.roles:
                    page.select_role(role["id"])
                    page.show_detail_tab(1)
                    self.settle(page)
                    path = page.learning_path
                    self.assertLessEqual(page.content.width(), page.width())
                    self.assertGreaterEqual(path.height(), path.heightForWidth(path.width()))
                    for step in path.steps:
                        self.assertTrue(path.rect().contains(step.geometry()))
                        self.assertEqual(step.title.y(), step.status.y())
                        for label in (step.title, step.status, step.caption):
                            self.assertGreaterEqual(label.height(), label.heightForWidth(label.width()))
                            self.assertTrue(step.rect().contains(label.geometry()))
                    self.assertEqual(path.outputs, tuple(role["outputs"]))
                if page.learning_path.steps:
                    page.scroll.ensureWidgetVisible(page.learning_path.steps[0], 0, 0)
                    self.settle(page)
                    self.assertFalse(page.learning_path.steps[0].visibleRegion().isEmpty())
                destination = os.environ.get("CAREER_LEARNING_EVIDENCE")
                if destination:
                    target = Path(destination)
                    target.mkdir(parents=True, exist_ok=True)
                    page.repaint()
                    guikit.pump(1)
                    self.assertTrue(page.grab().save(str(target / f"page-{mode}-{requested_width}.png")))
                    (target / "window-sizes.json").write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")

    def test_wrapped_connections_follow_number_order_and_avoid_card_interiors(self):
        path = self.path()
        for width in (656, 1184):
            self.resize_path(path, width)
            self.assertEqual([(a, b) for a, b, _ in path.connections], [(i, i + 1) for i in range(len(path.steps))])
            for i, _, points in path.connections:
                if path.columns > 1 and (i + 1) % path.columns == 0 and i + 1 < len(path.steps):
                    self.assertEqual(len(points), 6)
                    self.assertGreater(points[1].x(), path.steps[i].geometry().right())
                    self.assertLess(points[-2].x(), path.steps[i + 1].x())
                for a, b in zip(points, points[1:]):
                    for ratio in (.1, .5, .9):
                        point = a + (b - a) * ratio
                        self.assertTrue(QRectF(path.rect()).contains(point))
                        self.assertFalse(any(QRectF(step.geometry()).contains(point) for step in path.steps))

    def test_page_resize_font_theme_roundtrip_preserves_reading_step(self):
        page = CareerRoadmapPage(catalog=self.catalog)
        self.windows.append(page)
        page.resize(1280, 800)
        page.show()
        page.select_role("robot_policy")
        page.show_detail_tab(1)
        self.settle(page)
        step = page.learning_path.steps[3]
        page.scroll.ensureWidgetVisible(step)
        self.settle(page)
        page._remember()
        anchor, offset = page._anchor
        for width, text, mode in ((760, "larger", "dark"), (1280, "normal", "light")):
            page.resize(width, 800)
            theme.set_text(text)
            theme.set_mode(mode)
            kit.refont(page)
            self.settle(page)
            self.assertLessEqual(abs(anchor.mapTo(page.scroll.viewport(), QPoint()).y() - offset), 1)
            self.assertGreaterEqual(page.learning_path.height(), page.learning_path.heightForWidth(page.learning_path.width()))
            self.assertEqual(page.selected_role_id, "robot_policy")

    def test_empty_and_output_only_paths_have_no_fake_steps(self):
        for outputs in ((), ("결과 예시",)):
            path = CareerLearningPath((), outputs)
            self.windows.append(path)
            self.resize_path(path, 320)
            self.assertFalse(path.steps)
            self.assertFalse(path.connections)
            self.assertEqual(path.output.isHidden(), not outputs)

    def test_optional_capture_uses_only_synthetic_examples(self):
        destination = os.environ.get("CAREER_LEARNING_EVIDENCE")
        if not destination:
            self.skipTest("그림 저장 경로를 지정하지 않았음")
        target = Path(destination)
        target.mkdir(parents=True, exist_ok=True)
        theme.set_text("larger")
        for mode in ("light", "dark"):
            theme.set_mode(mode)
            for role in ("robot_control", "robot_policy"):
                path = self.path(role)
                for width in (656, 1184):
                    self.resize_path(path, width)
                    self.assertTrue(path.grab().save(str(target / f"{role}-{mode}-{width}.png")))
                    step = path.steps[1]
                    self.assertTrue(step.grab().save(str(target / f"{role}-{mode}-{width}-header.png")))
