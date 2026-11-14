"""직무를 바꿀 때 접근성 설명·그림과 좁은 화면의 글자 배치를 확인함."""
import unittest
from unittest.mock import patch

from tests import guikit
from PyQt6.QtCore import QRectF
from PyQt6.QtGui import QFontMetricsF

from career.catalog import load_catalog
from gui import theme
from gui.career_artifact import CareerArtifact, _Plate


# 같은 주제의 다른 직무가 잘못 연결돼도 잡도록 각 결과의 표식을 대조함.
RESULTS = {
    "robot_control": ("목표", "30도"), "robot_navigation": ("장애물", "돌아"),
    "robot_vision": ("볼트", "너트"), "field_integration": ("단선", "자동문"),
    "robot_policy": ("미도달", "정책 B"), "robot_backend": ("추가 0건", "17번"),
    "platform_infrastructure": ("점검 실패", "v1"), "frontend": ("연결 끊김", "R-02"),
    "backend": ("403", "403"), "data_engineering": ("재적재 후", "4행"),
    "qa": ("7자", "7자"),
}


class ArtifactTest(unittest.TestCase):
    def setUp(self):
        self.art = CareerArtifact()
        self.addCleanup(self.art.deleteLater)
        self.addCleanup(theme.set_mode, theme.state["mode"])
        self.addCleanup(theme.set_text, theme.state["text"])

    def test_catalog_switches_graphic_and_explanation_together(self):
        self.assertEqual({role["id"] for role in load_catalog().roles}, set(RESULTS))
        self.art.resize(630, 300)
        images = set()
        for role, (_, detail) in RESULTS.items():
            with self.subTest(role=role):
                self.art.set_role(role)
                self.assertIn(detail, self.art.accessibleDescription())
                self.assertIn("예시", self.art.accessibleDescription())
                self.assertIn("합성 예시", self.art.accessibleName())
                image = self.art.grab().toImage()
                body = image.copy(0, image.height() // 4, image.width(), image.height() * 3 // 4)
                images.add(body.constBits().asstring(body.sizeInBytes()))
        self.assertEqual(len(images), len(RESULTS))
        self.art.set_role("unknown")
        self.assertEqual(self.art.accessibleDescription(), "표시할 결과 예시가 없습니다.")
        self.art.set_role(None)
        self.assertNotIn("합성", self.art.accessibleName())

    def test_preferred_height_is_shared_across_roles(self):
        self.assertTrue(self.art.hasHeightForWidth())
        self.assertAlmostEqual(self.art.sizeHint().width() / self.art.sizeHint().height(), 2.1)
        for width, height in ((320, 180), (630, 300), (860, 340)):
            for role in RESULTS:
                self.art.set_role(role)
                self.assertEqual(self.art.heightForWidth(width), height)

    def test_painted_labels_fit_and_do_not_overlap(self):
        theme.set_text("larger")
        labels = []
        draw = _Plate.label

        def measure(plate, x, y, text, **options):
            draw(plate, x, y, text, **options)
            fm = QFontMetricsF(plate.p.font(), plate.p.device())
            width = fm.horizontalAdvance(text)
            offset = {"left": 0, "center": width / 2, "right": width}[options.get("align", "center")]
            center = plate.point(x, y)
            rect = QRectF(center.x() - offset, center.y() - fm.height() / 2, width, fm.height())
            labels.append((text, rect))

        with patch.object(_Plate, "label", measure):
            for width, height, mode in ((320, 180, "light"), (860, 340, "dark")):
                self.art.resize(width, height)
                theme.set_mode(mode)
                for role, (mark, _) in RESULTS.items():
                    with self.subTest(role=role, size=(width, height), mode=mode):
                        self.art.set_role(role)
                        labels.clear()
                        self.art.grab()
                        texts = [text for text, _ in labels]
                        self.assertIn("합성 예시", texts)
                        self.assertIn(mark, texts)
                        frame = QRectF(self.art.rect())
                        for i, (text, rect) in enumerate(labels):
                            self.assertTrue(frame.contains(rect), text)
                            for other, other_rect in labels[:i]:
                                self.assertFalse(rect.intersects(other_rect), (text, other))
