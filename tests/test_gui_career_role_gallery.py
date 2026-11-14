"""직무 목록의 실제 글자·배치·키 입력과 필터 뒤 선택 보존을 확인함."""
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tests import guikit
from PyQt6.QtCore import QEvent, QPoint, QRectF, Qt
from PyQt6.QtGui import QColor, QFontMetricsF, QImage, QKeyEvent
from PyQt6.QtTest import QSignalSpy, QTest
from PyQt6.QtWidgets import QAbstractButton, QScrollArea, QVBoxLayout, QWidget

from career.catalog import load_catalog
from gui import kit, theme
from gui.career_role_gallery import RoleCard, RoleGallery


class RoleGalleryTest(unittest.TestCase):
    def setUp(self):
        self.theme_state = dict(theme.state)
        self.roles = load_catalog().roles
        self.widgets = []

    def tearDown(self):
        for widget in self.widgets:
            widget.close()
            widget.deleteLater()
        guikit.pump()
        theme.set_text(self.theme_state["text"])
        theme.set_mode(self.theme_state["mode"], force=True)

    def show_gallery(self, width=760, height=480, roles=None):
        scroll = kit.page(QScrollArea())
        scroll.setWidgetResizable(True)
        content = QWidget()
        box = QVBoxLayout(content)
        box.setContentsMargins(kit.MARGIN, kit.MARGIN, kit.MARGIN, kit.MARGIN)
        gallery = RoleGallery()
        box.addWidget(gallery)
        box.addStretch()
        gallery.set_roles(self.roles if roles is None else roles)
        scroll.setWidget(content)
        scroll.resize(width, height)
        self.widgets.append(scroll)
        scroll.show()
        self.settle(scroll, gallery)
        return scroll, gallery

    def settle(self, scroll, gallery):
        previous = None
        stable = 0

        def ready():
            nonlocal previous, stable
            state = (scroll.size(), scroll.viewport().size(), gallery.size(), gallery.columns,
                     tuple((key, card.geometry()) for key, card in gallery.cards.items()))
            stable = stable + 1 if state == previous else 0
            previous = state
            return stable >= 2 and gallery.height() >= gallery.heightForWidth(gallery.width())

        guikit.wait_until(ready, timeout=3)

    def evidence(self, name, scroll, gallery):
        directory = os.environ.get("CAREER_GALLERY_EVIDENCE")
        if not directory:
            return
        target = Path(directory)
        target.mkdir(parents=True, exist_ok=True)
        self.assertTrue(scroll.grab().save(str(target / f"{name}-viewport.png")))
        self.assertTrue(gallery.grab().save(str(target / f"{name}-gallery.png")))
        data = {"window": [scroll.width(), scroll.height()], "gallery": [gallery.width(), gallery.height()],
                "columns": gallery.columns, "font": theme.TYPE["body"], "theme": theme.state["scheme"],
                "cards": {key: {"card": card.geometry().getRect(),
                                "text": {name: rect.getRect() for name, rect in card.text_rects.items()}}
                          for key, card in gallery.cards.items()}}
        (target / f"{name}-geometry.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def ink_rows(self, image, rect, tone, antialias=False):
        ratio = image.devicePixelRatioF()
        left, right = round(rect.left() * ratio), round(rect.right() * ratio)
        top, bottom = round(rect.top() * ratio), round(rect.bottom() * ratio)
        background = image.pixelColor(left, top).getRgb()[:3]
        target = theme.qcolor(tone).getRgb()[:3]
        direction = tuple(t - b for t, b in zip(target, background))
        length = sum(d * d for d in direction)

        def visible_ink(color):
            if guikit.near(color, tone):
                return True
            if not antialias or not length:
                return False
            # 가는 획이 배경과 섞인 화소를 확인함. 빈 배경과 다른 색은 제외함.
            change = tuple(c - b for c, b in zip(color.getRgb()[:3], background))
            coverage = sum(c * d for c, d in zip(change, direction)) / length
            residual = max(abs(c - coverage * d) for c, d in zip(change, direction))
            return .5 <= coverage <= 1 and residual <= 8

        return [y / ratio for y in range(top, min(bottom, image.height()))
                if any(visible_ink(image.pixelColor(x, y))
                       for x in range(left, min(right, image.width())))]

    def test_text_ink_accepts_blended_strokes_but_rejects_empty_background(self):
        image = QImage(30, 30, QImage.Format.Format_RGB32)
        rect = QRectF(0, 0, 30, 30)
        for mode in ("light", "dark"):
            theme.set_mode(mode)
            background, target = theme.qcolor("surface"), theme.qcolor("muted")
            image.fill(background)
            self.assertEqual(self.ink_rows(image, rect, "muted", antialias=True), [])
            mixed = QColor(*(round(b + .85 * (t - b)) for b, t in
                             zip(background.getRgb()[:3], target.getRgb()[:3])))
            image.setPixelColor(10, 12, mixed)
            self.assertEqual(self.ink_rows(image, rect, "muted", antialias=True), [12])

    def assert_text_fits(self, card):
        self.assertIsInstance(card, QAbstractButton)
        self.assertTrue(card.property("reading_anchor"))
        self.assertEqual(card.text(), card.role["title"])
        self.assertTrue(card.accessibleDescription().startswith(card.role["outputs"][0]))
        self.assertEqual(card.font().pixelSize(), theme.TYPE["body"][0])
        image = card.grab().toImage()
        rects = card.text_rects
        for name, text, font, tone in (("title", card.role["title"], card.font(), "ink"),
                                       ("output", card.role["outputs"][0], theme.font("caption"), "muted")):
            rect = rects[name]
            self.assertTrue(QRectF(card.rect()).contains(rect), (text, card.size(), rect))
            self.assertFalse(rect.intersects(card.image_rect))
            bound = QFontMetricsF(font).boundingRect(QRectF(0, 0, rect.width(), 10000),
                                                    Qt.TextFlag.TextWordWrap.value, text)
            self.assertLessEqual(bound.height(), rect.height() + 1, text)
            self.assertLessEqual(bound.width(), rect.width() + 1, text)
            rows = self.ink_rows(image, rect, tone, antialias=True)
            self.assertTrue(rows, (name, text))
            self.assertGreater(rows[0], rect.top())
            self.assertLess(rows[-1], rect.bottom() - 1)
        self.assertEqual(rects["output"].top() - rects["title"].bottom(), theme.GAP["title_description"])

    def test_max_font_small_and_wide_in_both_themes(self):
        theme.set_text("larger")
        self.assertEqual(len(self.roles), 11)
        for mode in ("light", "dark"):
            theme.set_mode(mode)
            for width, height, columns in ((760, 480, 1), (1280, 800, 3)):
                with self.subTest(mode=mode, width=width):
                    scroll, gallery = self.show_gallery(width, height)
                    self.assertEqual((scroll.width(), scroll.height()), (width, height))
                    self.assertEqual(gallery.columns, columns)
                    self.assertEqual(scroll.horizontalScrollBar().maximum(), 0)
                    cards = list(gallery.cards.values())
                    gallery.clearFocus()
                    for card in cards:
                        card.clearFocus()
                    self.evidence(f"{mode}-{width}-maxfont", scroll, gallery)
                    first_ink = {}
                    for i, card in enumerate(cards):
                        self.assert_text_fits(card)
                        self.assertLessEqual(card.geometry().right(), gallery.width())
                        self.assertLessEqual(card.image_rect.height(), 160)
                        if columns == 1:
                            self.assertLess(card.image_rect.right(), card.text_rects["title"].left())
                        else:
                            self.assertLess(card.image_rect.bottom(), card.text_rects["title"].top())
                        image = card.grab().toImage()
                        ink = self.ink_rows(image, card.text_rects["output"], "muted", antialias=True)[0]
                        first_ink[i] = ink + card.y()
                        if i % columns:
                            previous = cards[i - 1]
                            self.assertEqual(card.y(), previous.y())
                            self.assertEqual(card.height(), previous.height())
                            self.assertEqual(card.text_rects["title"].top(), previous.text_rects["title"].top())
                            self.assertEqual(card.text_rects["output"].top(), previous.text_rects["output"].top())
                            self.assertLessEqual(abs(first_ink[i] - first_ink[i - 1]), 2)
                        scroll.ensureWidgetVisible(card, 0, 0)
                        guikit.pump(1)
                        top = card.mapTo(scroll.viewport(), QPoint(0, 0)).y()
                        self.assertGreaterEqual(top, 0)
                        self.assertLessEqual(top + card.height(), scroll.viewport().height())
                    if columns == 1:
                        self.assertLess(cards[2].y() + cards[2].text_rects["title"].bottom(), 480 - 2 * kit.MARGIN)
                    scroll.close()

    def test_keys_and_whole_tile_emit_once_without_saving(self):
        scroll, gallery = self.show_gallery()
        spy = QSignalSpy(gallery.picked)
        card = gallery.cards[self.roles[0]["id"]]
        card.setFocus(Qt.FocusReason.TabFocusReason)
        guikit.wait_until(card.hasFocus)
        for key in (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            before = len(spy)
            QTest.keyPress(card, key)
            repeat = QKeyEvent(QEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier, "", True)
            guikit.APP.sendEvent(card, repeat)
            QTest.keyRelease(card, key)
            self.assertEqual(len(spy), before + 1)
            self.assertEqual(spy[-1][0], card.role["id"])
            self.assertTrue(card.isChecked())
            self.assertFalse(card.saved)
        for position in (card.image_rect.center(), card.text_rects["title"].center(), card.text_rects["output"].center()):
            before = len(spy)
            QTest.mouseClick(card, Qt.MouseButton.LeftButton, pos=position.toPoint())
            self.assertEqual(len(spy), before + 1)
        QTest.keyClick(card, Qt.Key.Key_Tab)
        guikit.wait_until(lambda: gallery.cards[self.roles[1]["id"]].hasFocus())
        self.assertEqual(gallery.saved_role_id, "")
        before = len(spy)
        card.setEnabled(False)
        QTest.keyClick(card, Qt.Key.Key_Return)
        QTest.mouseClick(card, Qt.MouseButton.LeftButton)
        self.assertEqual(len(spy), before)

    def test_focus_ring_changes_pixels_without_moving_text(self):
        for mode in ("light", "dark"):
            theme.set_mode(mode)
            scroll, gallery = self.show_gallery(760, 480, self.roles[:2])
            card, other = gallery.cards.values()
            other.setFocus()
            guikit.wait_until(other.hasFocus)
            plain = card.grab().toImage()
            text_rects = card.text_rects
            card.setFocus(Qt.FocusReason.TabFocusReason)
            guikit.wait_until(card.hasFocus)
            focused = card.grab().toImage()
            self.assertEqual(card.text_rects, text_rects)
            edge = QRectF(24, 0, card.width() - 48, 5)
            self.assertFalse(self.ink_rows(plain, edge, "focus"))
            self.assertTrue(self.ink_rows(focused, edge, "focus"))
            for rect in text_rects.values():
                ratio = plain.devicePixelRatioF()
                pixels = QRectF(rect.x() * ratio, rect.y() * ratio, rect.width() * ratio, rect.height() * ratio).toAlignedRect()
                self.assertEqual(plain.copy(pixels), focused.copy(pixels))
            self.evidence(f"{mode}-focus", scroll, gallery)
            scroll.close()

    def test_filter_retains_selection_and_saved_role_separately(self):
        original = copy.deepcopy(self.roles)
        scroll, gallery = self.show_gallery()
        spy = QSignalSpy(gallery.picked)
        chosen, saved = self.roles[-1]["id"], self.roles[0]["id"]
        gallery.set_selected(chosen)
        gallery.set_saved(saved)
        kept = gallery.cards[chosen]
        gallery.set_roles([self.roles[-1]])
        self.assertIs(gallery.cards[chosen], kept)
        self.assertTrue(kept.isChecked())
        self.assertFalse(kept.saved)
        gallery.set_roles(self.roles[1:3])
        self.assertEqual(gallery.selected_role_id, chosen)
        self.assertEqual(gallery.saved_role_id, saved)
        self.assertFalse(any(card.isChecked() or card.saved for card in gallery.cards.values()))
        gallery.set_roles([])
        self.assertEqual(gallery.cards, {})
        self.assertEqual(gallery.heightForWidth(gallery.width()), 0)
        self.assertEqual(gallery.minimumHeight(), 0)
        gallery.set_roles(self.roles)
        self.assertTrue(gallery.cards[chosen].isChecked())
        self.assertTrue(gallery.cards[saved].saved)
        self.assertIn("관심 직무", gallery.cards[saved].accessibleDescription())
        gallery.cards[chosen].click()
        self.assertEqual(len(spy), 1)
        self.assertTrue(gallery.cards[saved].saved)
        self.assertFalse(gallery.cards[chosen].saved)
        gallery.set_saved(None)
        self.assertFalse(any(card.saved for card in gallery.cards.values()))
        self.assertEqual(self.roles, original)

    def test_refont_and_resize_reflow_and_preserve_states(self):
        theme.set_text("normal")
        scroll, gallery = self.show_gallery()
        chosen = self.roles[4]["id"]
        gallery.set_selected(chosen)
        gallery.set_saved(chosen)
        normal_columns = gallery.columns
        for step, width, height in (("larger", 760, 480), ("larger", 1280, 800), ("normal", 760, 480)):
            theme.set_text(step)
            gallery.refont()
            scroll.resize(width, height)
            self.settle(scroll, gallery)
            self.assertEqual(scroll.horizontalScrollBar().maximum(), 0)
            card = gallery.cards[chosen]
            self.assertTrue(card.saved)
            self.assertTrue(card.isChecked())
            for item in gallery.cards.values():
                self.assert_text_fits(item)
            if step == "larger" and width == 760:
                self.assertLess(gallery.columns, normal_columns)
            if step == "normal":
                self.assertEqual(gallery.columns, normal_columns)

    def test_missing_and_corrupt_images_remain_operable(self):
        theme.set_text("larger")
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / f"{self.roles[1]['id']}.webp").write_bytes(b"invalid image")
            with patch("gui.career_role_gallery.SCENES", Path(directory)):
                scroll, gallery = self.show_gallery(760, 480, self.roles[:2])
            spy = QSignalSpy(gallery.picked)
            for card in gallery.cards.values():
                self.assertTrue(card.image.isNull())
                self.assert_text_fits(card)
                image = card.grab().toImage()
                self.assertTrue(self.ink_rows(image, card.image_rect, "border_strong"))
                QTest.mouseClick(card, Qt.MouseButton.LeftButton, pos=card.image_rect.center().toPoint())
            self.assertEqual([entry[0] for entry in spy], [role["id"] for role in self.roles[:2]])
            self.evidence("missing-corrupt", scroll, gallery)


if __name__ == "__main__":
    unittest.main()
