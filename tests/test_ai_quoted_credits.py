"""가져온 짧은 장면의 허락과 전체 시간 및 기존 출처 검사를 대조함."""
import json
from pathlib import Path
import struct
import tempfile
import unittest
import zlib

from tools import ai_art, verify_ai


def png(width=2):
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    header = struct.pack(">IIBBBBB", width, 1, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(b"\0" * (1 + width * 3))) + chunk(b"IEND", b"")


class Messages:
    def __init__(self):
        self.failures = []

    def fail(self, label, step, text):
        self.failures.append((label, step, text))

    def warn(self, label, step, text):
        pass


class QuotedCreditsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.pages = []
        self.manifest = self.root / "manifest.json"
        self.manifest.write_text('{"format": 1, "files": {}}')

    def credit(self, seconds=7.073733, **changes):
        row = {"file": "assets/clip.png", "license": verify_ai.QUOTED_CLIP_LICENSE,
               "author": verify_ai.QUOTED_CLIP_AUTHOR, "url": verify_ai.QUOTED_CLIP_URLS[0],
               "permission_url": verify_ai.QUOTED_CLIP_PERMISSION, "source_seconds": seconds}
        row.update(changes)
        return row

    def page(self, page_id, credits, caption="출처: 3Blue1Brown의 공식 글입니다.", width=2):
        folder = self.root / "learn" / page_id
        (folder / "assets").mkdir(parents=True, exist_ok=True)
        (folder / "assets/clip.png").write_bytes(png(width))
        meta = {"sections": {page_id[1:] + "a": "예를 봅니다"}, "credits": credits}
        (folder / "meta.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
        (folder / "page.md").write_text("# 예\n\n## 예를 봅니다\n\n### 값을 읽습니다\n\n```figure\n파일: assets/clip.png\n캡션: " + caption + "\n내용: 값입니다.\n```\n", encoding="utf-8")
        if page_id not in self.pages:
            self.pages.append(page_id)
        return folder

    def check(self):
        messages = Messages()
        verify_ai.check_figures(messages, str(self.root), {"pages": [{"id": key} for key in self.pages]}, str(self.manifest))
        return messages.failures

    def test_verified_two_assets_pass(self):
        self.page("l90", [self.credit()])
        self.page("l91", [self.credit(2.5025, url=verify_ai.QUOTED_CLIP_URLS[1])])
        self.assertEqual([], self.check())

    def test_author_permission_and_asset_must_match(self):
        cases = ({"author": "Grant Sanderson"}, {"permission_url": "https://example.org/permission"},
                 {"permission_url": verify_ai.QUOTED_CLIP_PERMISSION + "?allowed=true"},
                 {"url": "https://example.org/network-propagation.mp4"},
                 {"url": verify_ai.QUOTED_CLIP_URLS[0] + "?copy=true"})
        for change in cases:
            with self.subTest(change=change):
                self.page("l90", [self.credit(**change)])
                self.assertTrue(self.check())

    def test_general_permission_phrase_is_not_a_license(self):
        self.page("l90", [self.credit(license="허락 있음")])
        self.assertTrue(self.check())

    def test_official_assets_cannot_be_relabelled_as_cc(self):
        for license_name in verify_ai.ALLOWED_LICENSES:
            with self.subTest(license_name=license_name):
                self.page("l90", [self.credit(license=license_name)])
                self.assertTrue(any("허락 이름" in message for _, _, message in self.check()))

    def test_duration_rejects_non_numeric_nonfinite_and_boundaries(self):
        for seconds in (None, True, False, "7.0", 0, -1, 60, float("nan"), float("inf")):
            with self.subTest(seconds=seconds):
                self.page("l90", [self.credit(seconds)])
                self.assertTrue(self.check())
        self.page("l90", [self.credit(59.999)])
        self.assertEqual([], self.check())

    def test_total_is_across_pages_and_strictly_below_sixty(self):
        self.page("l90", [self.credit(30)])
        self.page("l91", [self.credit(30, url=verify_ai.QUOTED_CLIP_URLS[1])])
        self.assertTrue(any("합계" in message for _, _, message in self.check()))
        self.page("l91", [self.credit(29.999, url=verify_ai.QUOTED_CLIP_URLS[1])])
        self.assertEqual([], self.check())

    def test_unreferenced_and_duplicate_credit_rows_still_count(self):
        for second_file in ("assets/unused.png", "assets/clip.png"):
            with self.subTest(second_file=second_file):
                self.page("l90", [self.credit(30), self.credit(30, file=second_file)])
                self.assertTrue(any("합계" in message for _, _, message in self.check()))

    def test_metadata_without_page_still_counts_toward_total(self):
        self.page("l90", [self.credit(30)])
        folder = self.page("l91", [self.credit(30)])
        (folder / "page.md").unlink()
        self.assertTrue(any("합계" in message for _, _, message in self.check()))

    def test_imported_clip_cannot_be_registered_as_drawn(self):
        folder = self.page("l90", [self.credit()])
        entry = {"format": 1, "files": {"learn/l90/assets/clip.png": {"sha256": ai_art.file_sha(str(folder / "assets/clip.png"))}}}
        self.manifest.write_text(json.dumps(entry))
        self.assertTrue(any("인용 자산" in message for _, _, message in self.check()))

    def test_standard_licenses_keep_their_existing_requirements(self):
        for license_name in verify_ai.ALLOWED_LICENSES:
            with self.subTest(license_name=license_name):
                self.page("l90", [{"file": "assets/clip.png", "license": license_name, "author": "기존 저자", "url": "https://example.org/image"}])
                self.assertEqual([], self.check())
        self.page("l90", [{"file": "assets/clip.png", "license": "CC BY 4.0", "url": "https://example.org/image"}])
        self.assertTrue(self.check())

    def test_caption_credit_and_image_limits_still_apply(self):
        self.page("l90", [self.credit()], caption="값을 봅니다.")
        self.assertTrue(any("출처" in message for _, _, message in self.check()))
        self.page("l90", [self.credit()], width=1121)
        self.assertTrue(any("한도 1120" in message for _, _, message in self.check()))


if __name__ == "__main__":
    unittest.main()
