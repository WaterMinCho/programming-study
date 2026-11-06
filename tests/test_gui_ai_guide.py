# -*- coding: utf-8 -*-
"""사용 안내의 좌표·넘김·확대·입력 복원과 작은 창 배치를 offscreen에서 확인함."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

from tests import guikit

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QFontMetricsF, QTextCursor
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QLineEdit, QPlainTextEdit, QWidget

from gui import ai_guide, kit, theme


class GuideTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ai_guide_")
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        # 실제 문서에 있는 화면을 검사 입력으로 복사함. 제품 안내의 캡처로 넣지 않음.
        self.image = self.folder / "screen.png"
        shutil.copyfile(Path(guikit.ROOT) / "docs/img/home.png", self.image)
        self.data = {"version": 1, "steps": [
            {"id": "step-%d" % n, "title": "화면에서 학습할 위치를 확인합니다",
             "description": "표시한 번호의 버튼을 확인합니다. 창을 줄여도 설명은 그림 밖에서 읽습니다.",
             "image": "screen.png", "targets": [
                 {"x": 30, "y": 40, "width": 200, "height": 100,
                  "label": "여기서 다음 행동을 확인합니다."}]} for n in range(4)]}
        self.manifest = self.folder / "manifest.json"
        self.write_manifest()
        self.owner = QWidget()
        self.owner.resize(1280, 800)
        self.owner.show()
        self.owner.activateWindow()
        guikit.pump()
        self.dialog = None
        self.old_mode, self.old_text = theme.state["mode"], theme.state["text"]

    def tearDown(self):
        if self.dialog is not None:
            if self.dialog.large_dialog is not None:
                self.dialog.large_dialog.close()
            self.dialog.close()
        guikit.pump()
        self.owner.close()
        self.owner.deleteLater()
        theme.set_mode(self.old_mode)
        theme.set_text(self.old_text)
        guikit.pump()

    def write_manifest(self):
        self.manifest.write_text(json.dumps(self.data, ensure_ascii=False), encoding="utf-8")

    def open(self):
        self.dialog = ai_guide.open_guide(self.owner, self.manifest)
        guikit.pump()
        return self.dialog

    def test_real_png_stays_unchanged_and_marks_follow_its_aspect(self):
        original = hashlib.sha256(self.image.read_bytes()).hexdigest()
        dialog = self.open()
        view = dialog.image
        view.resize(640, 400)
        image = view.image_rect()
        self.assertAlmostEqual(image.width() / image.height(), view.pixmap.width() / view.pixmap.height())
        target = view.step["targets"][0]
        drawn = view.target_rect(target)
        self.assertAlmostEqual((drawn.left() - image.left()) / image.width(), 30 / view.pixmap.width())
        self.assertAlmostEqual(drawn.width() / image.width(), 200 / view.pixmap.width())
        rendered = view.grab().toImage()
        point = QPoint(round(drawn.center().x()), round(drawn.top() + 2))
        self.assertTrue(guikit.near(rendered.pixelColor(point), "primary"))
        self.assertEqual(hashlib.sha256(self.image.read_bytes()).hexdigest(), original)

    def test_published_guide_numbers_do_not_cover_the_target_buttons(self):
        for step in ai_guide.load_steps(ai_guide.MANIFEST):
            view = ai_guide.ScreenshotView(step)
            for width in (640, 1280, 3000):
                view.resize(width, view.heightForWidth(width))
                for target in step["targets"]:
                    marker = view.badge_rect(target)
                    self.assertTrue(view.image_rect().contains(marker), step["id"])
                    self.assertFalse(marker.intersects(view.target_rect(target)), (step["id"], target["label"]))
            view.deleteLater()

    def test_navigation_is_bounded_and_keeps_the_dialog_open(self):
        dialog = self.open()
        self.assertFalse(dialog.previous.isEnabled())
        for n in range(1, 4):
            guikit.click(dialog.next_btn)
            self.assertEqual(dialog.counter.text(), "%d / 4" % (n + 1))
        self.assertFalse(dialog.next_btn.isEnabled())
        self.assertTrue(dialog.isVisible())
        dialog.show_step(4)
        self.assertEqual(dialog.position, 3)
        guikit.click(dialog.previous)
        self.assertEqual(dialog.position, 2)
        self.assertIs(ai_guide.open_guide(self.owner, self.manifest), dialog)

    def test_large_view_uses_source_pixels_and_scrolls_at_small_size(self):
        self.owner.resize(760, 480)
        dialog = self.open()
        guikit.click(dialog.large_btn)
        large = dialog.large_dialog
        self.assertEqual(large.view.width(), large.view.pixmap.width())
        self.assertGreater(large.scroll.horizontalScrollBar().maximum(), 0)
        ratio = large.view.width() / large.view.height()
        guikit.click(large.plus)
        self.assertEqual(large.percent.text(), "125%")
        self.assertAlmostEqual(large.view.width() / large.view.height(), ratio, places=2)
        guikit.click(large.close_btn)
        self.assertTrue(dialog.isVisible())

    def test_controls_fit_and_stay_outside_scrolling_content(self):
        for size in [(760, 480), (1024, 700), (1280, 800)]:
            for text in ("normal", "larger"):
                for mode in ("light", "dark"):
                    with self.subTest(size=size, text=text, mode=mode):
                        theme.set_text(text)
                        theme.set_mode(mode)
                        self.owner.resize(*size)
                        dialog = self.open()
                        # 기본 가상 화면이 작아도 대화상자 자체의 요청 크기로 배치를 확인함.
                        dialog.resize(min(1040, size[0]), min(760, size[1]))
                        guikit.pump()
                        self.assertEqual((dialog.width(), dialog.height()), (min(1040, size[0]), min(760, size[1])))
                        self.assertLess(dialog.scroll.geometry().bottom(), dialog.controls.geometry().top())
                        self.assertEqual(dialog.scroll.horizontalScrollBar().maximum(), 0)
                        for button in (dialog.large_btn, dialog.previous, dialog.next_btn, dialog.close_btn):
                            box = button.geometry().translated(button.parentWidget().mapTo(dialog, QPoint()))
                            self.assertTrue(dialog.rect().contains(box), (button.text(), box))
                            self.assertGreater(button.width(), QFontMetricsF(button.font()).horizontalAdvance(button.text()))
                        dialog.scroll.verticalScrollBar().setValue(dialog.scroll.verticalScrollBar().maximum())
                        self.assertTrue(dialog.close_btn.isVisible())
                        dialog.close()
                        guikit.pump()
                        self.dialog = None

    def test_modal_close_restores_input_selection_and_reading_position(self):
        inner = QWidget()
        layout = kit.box(inner, spacing=24)
        for n in range(12):
            layout.addWidget(kit.label("설명을 읽습니다."))
        field = QLineEdit("읽던 입력 내용을 유지합니다")
        layout.addWidget(field)
        for n in range(20):
            layout.addWidget(kit.label("다음 설명을 읽습니다."))
        scroll = kit.scroll(inner)
        kit.box(self.owner).addWidget(scroll)
        guikit.pump()
        field.setFocus()
        field.setSelection(8, -5)
        scroll.verticalScrollBar().setValue(220)
        guikit.pump()
        before = (field.text(), field.selectedText(), field.cursorPosition(), scroll.verticalScrollBar().value())
        dialog = self.open()
        guikit.click(dialog.next_btn)
        QTest.keyClick(dialog, Qt.Key.Key_Escape)
        guikit.pump()
        self.dialog = None
        self.assertEqual((field.text(), field.selectedText(), field.cursorPosition(), scroll.verticalScrollBar().value()), before)
        self.assertIs(guikit.APP.focusWidget(), field)

    def test_text_cursor_anchor_and_inner_scroll_are_preserved(self):
        editor = QPlainTextEdit("\n".join("입력한 문장을 보관합니다." for n in range(100)))
        kit.box(self.owner).addWidget(editor)
        guikit.pump()
        editor.setFocus()
        cursor = editor.textCursor()
        cursor.setPosition(100)
        cursor.setPosition(80, QTextCursor.MoveMode.KeepAnchor)
        editor.setTextCursor(cursor)
        editor.verticalScrollBar().setValue(3)
        before = (cursor.anchor(), cursor.position(), editor.verticalScrollBar().value(), editor.toPlainText())
        dialog = self.open()
        dialog.close()
        guikit.pump()
        self.dialog = None
        current = editor.textCursor()
        self.assertEqual((current.anchor(), current.position(), editor.verticalScrollBar().value(), editor.toPlainText()), before)

    def test_missing_image_and_outside_coordinates_do_not_show_a_valid_picture(self):
        self.data["steps"][0]["image"] = "missing.png"
        self.write_manifest()
        dialog = self.open()
        self.assertTrue(dialog.image.error)
        self.assertFalse(dialog.large_btn.isEnabled())
        guikit.click(dialog.next_btn)
        self.assertFalse(dialog.image.error)
        dialog.close()
        guikit.pump()
        self.dialog = None
        self.data["steps"][0]["image"] = "screen.png"
        self.data["steps"][0]["targets"][0]["x"] = 999999
        self.write_manifest()
        dialog = self.open()
        self.assertTrue(dialog.image.error)
        self.assertFalse(dialog.large_btn.isEnabled())

    def test_invalid_manifest_is_visible_without_a_fake_image(self):
        for value in ("../outside.png", "https://example.com/screen.png"):
            self.data["steps"][0]["image"] = value
            self.write_manifest()
            with self.assertRaises(ai_guide.GuideError):
                ai_guide.load_steps(self.manifest)
        self.manifest.unlink()
        dialog = self.open()
        self.assertEqual(dialog.steps, [])
        self.assertFalse(dialog.large_btn.isEnabled())
        self.assertFalse(dialog.next_btn.isEnabled())

    def test_home_button_opens_only_the_guide(self):
        from gui.ai_home import AiHomePage
        home = AiHomePage(mock.Mock())
        kit.box(self.owner).addWidget(home)
        guikit.pump()
        with mock.patch.object(ai_guide, "open_guide") as opened:
            guikit.click(home.guide_btn)
            opened.assert_called_once_with(home)
        self.assertEqual(home.guide_btn.text(), "학습·사용 안내")


if __name__ == "__main__":
    unittest.main()
