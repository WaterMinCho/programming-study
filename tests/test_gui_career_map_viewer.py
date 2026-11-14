"""지도에서 읽던 지점과 창 상태를 실제 입력 이벤트로 확인함."""
import unittest
from unittest.mock import Mock

from tests import guikit
from PyQt6.QtCore import QPoint, QPointF, Qt
from PyQt6.QtGui import QColor, QNativeGestureEvent, QPainter, QPointingDevice, QWheelEvent
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QAbstractScrollArea

from gui import motion
from gui.career_roadmap import CareerRoadmapPage


class MapViewerTest(unittest.TestCase):
    def setUp(self):
        self.page = CareerRoadmapPage(on_select_goal=Mock())
        self.page.select_role("robot_control")
        self.page.show_detail_tab(1)
        self.page.resize(640, 460)
        self.page.show()
        guikit.pump()
        self.page.scroll.ensureWidgetVisible(self.page.image_button)
        self.page.image_button.setFocus()
        guikit.click(self.page.image_button)
        self.dialog = self.page.image_dialog
        self.view = self.dialog.area
        self.viewport = self.view.viewport()

    def tearDown(self):
        if self.page.image_dialog is not None:
            self.page.image_dialog.close()
        self.page.close()
        self.page.deleteLater()
        guikit.pump()

    def wheel(self, point, modifier, angle=0, pixel=QPoint()):
        local = QPointF(point)
        event = QWheelEvent(local, self.viewport.mapToGlobal(local), pixel, QPoint(0, angle),
                            Qt.MouseButton.NoButton, modifier, Qt.ScrollPhase.ScrollUpdate, False)
        guikit.APP.sendEvent(self.viewport, event)
        guikit.pump()

    def test_wheel_and_native_pinch_keep_map_point_and_drag_scrolls(self):
        view = self.view
        self.assertEqual(self.dialog.findChildren(QAbstractScrollArea), [view])
        bar = view.verticalScrollBar()
        bar.setValue(bar.maximum() // 2)
        pointer = QPoint(self.viewport.width() // 3, self.viewport.height() // 4)
        for modifier in (Qt.KeyboardModifier.ControlModifier, Qt.KeyboardModifier.MetaModifier):
            before = view.source_point(pointer)
            scale = view.scale
            self.wheel(pointer, modifier, angle=120)
            self.assertGreater(view.scale, scale)
            self.assertLess((view.source_point(pointer) - before).manhattanLength() * view.scale, 1.5)
        before = view.source_point(pointer)
        local = QPointF(pointer)
        pinch = QNativeGestureEvent(Qt.NativeGestureType.ZoomNativeGesture, QPointingDevice.primaryPointingDevice(),
                                    2, local, self.viewport.mapTo(self.dialog, local),
                                    self.viewport.mapToGlobal(local), 0.1, QPointF())
        scale = view.scale
        guikit.APP.sendEvent(self.viewport, pinch)
        self.assertAlmostEqual(view.scale, scale * 1.1)
        self.assertLess((view.source_point(pointer) - before).manhattanLength() * view.scale, 1.5)
        x, y = view.horizontalScrollBar(), bar
        before = x.value(), y.value()
        guikit.drag(self.viewport, -28, -41)
        self.assertEqual((x.value(), y.value()), (before[0] + 28, before[1] + 41))
        scale, start = view.scale, y.value()
        self.wheel(pointer, Qt.KeyboardModifier.NoModifier, pixel=QPoint(-7, -35))
        self.assertEqual(y.value(), start + 35)
        self.wheel(pointer, Qt.KeyboardModifier.NoModifier, angle=-120)
        self.assertGreater(y.value(), start + 35)
        self.assertEqual(view.scale, scale)

    def test_bottom_corner_matches_original_and_reopening_releases_old_canvas(self):
        from PyQt6 import sip

        view = self.view
        # 원본 끝이 빈 여백이어도 모서리의 이동과 색 보존을 확인할 표식을 넣음.
        view.original = view.original.copy()
        painter = QPainter(view.original)
        painter.fillRect(view.original.width() - 120, view.original.height() - 80,
                         80, 40, QColor("#5279a3"))
        painter.end()
        view.zoom(1)
        guikit.pump()
        for bar in (view.horizontalScrollBar(), view.verticalScrollBar()):
            bar.setValue(bar.maximum())
        source = view.original.toImage()
        offset = QPoint(source.width() - self.viewport.width(), source.height() - self.viewport.height())
        shot = self.viewport.grab().toImage()
        ratio = shot.devicePixelRatio()
        # 원본의 끝 여백과 본문 상자를 함께 비교함.
        samples = set()
        for y in range(8, self.viewport.height() - 4, 11):
            for x in range(8, self.viewport.width() - 4, 13):
                sx, sy = x + offset.x(), y + offset.y()
                original = source.pixelColor(sx, sy)
                if all(source.pixelColor(sx + dx, sy + dy) == original
                       for dx in (-1, 0, 1) for dy in (-1, 0, 1)):
                    pixel = shot.pixelColor(int((x + 0.5) * ratio), int((y + 0.5) * ratio))
                    self.assertEqual(pixel.name(), original.name(), (x, y))
                    samples.add(original.name())
        self.assertGreaterEqual(len(samples), 2)
        expected = QPointF(source.width(), source.height())
        end = view.source_point(QPoint(self.viewport.width(), self.viewport.height()))
        self.assertEqual(end, expected)
        self.dialog.reject()
        guikit.wait_until(lambda: sip.isdeleted(view))
        previous = motion.enabled
        self.addCleanup(setattr, motion, "enabled", previous)
        motion.enabled = True
        self.page.open_image()
        dialog = self.page.image_dialog
        guikit.wait_until(lambda: dialog.graphicsEffect() is None)
        dialog.reject()
        guikit.wait_until(lambda: self.page.image_dialog is None and sip.isdeleted(dialog))

    def test_restore_resize_fit_keys_and_escape_return_to_opener(self):
        view, dialog = self.view, self.dialog
        self.assertTrue(dialog.isMaximized())
        guikit.click(dialog.window_size)
        self.assertFalse(dialog.isMaximized())
        self.assertEqual(dialog.window_size.text(), "창 최대화")
        dialog.resize(610, 420)
        guikit.pump()
        size = dialog.size()
        self.assertAlmostEqual(view.scale * view.original.width(), self.viewport.width(), delta=1)
        guikit.click(dialog.window_size)
        self.assertTrue(dialog.isMaximized())
        guikit.click(dialog.window_size)
        self.assertEqual(dialog.size(), size)
        view.setFocus()
        fit = view.scale
        QTest.keyClick(view, Qt.Key.Key_Plus)
        self.assertAlmostEqual(view.scale, fit * view.STEP)
        QTest.keyClick(view, Qt.Key.Key_Minus)
        self.assertAlmostEqual(view.scale, fit)
        dialog.resize(555, 405)
        guikit.pump()
        self.assertAlmostEqual(view.scale, fit)
        QTest.keyClick(view, Qt.Key.Key_F)
        self.assertAlmostEqual(view.scale * view.original.width(), self.viewport.width(), delta=1)
        bar = view.verticalScrollBar()
        start = bar.value()
        QTest.keyClick(view, Qt.Key.Key_PageDown)
        self.assertGreater(bar.value(), start)
        QTest.keyClick(view, Qt.Key.Key_Up)
        self.assertLess(bar.value(), start + bar.pageStep())
        role, pos = self.page.selected_role_id, self.page.scroll.verticalScrollBar().value()
        QTest.keyClick(view, Qt.Key.Key_Escape)
        guikit.pump()
        self.assertIsNone(self.page.image_dialog)
        self.assertEqual(self.page.selected_role_id, role)
        self.assertEqual(self.page.scroll.verticalScrollBar().value(), pos)
        self.assertIs(self.page.window().focusWidget(), self.page.image_button)
