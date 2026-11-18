# -*- coding: utf-8 -*-
"""작은 회차 화면의 제목·편집기·실행 결과와 입력 보존을 확인함."""
import json
import os
from pathlib import Path

from tests import guikit, test_gui

from PyQt6.QtCore import QPoint
from PyQt6.QtGui import QTextCursor
from PyQt6.QtTest import QSignalSpy

from gui import round_page, theme


class RoundLayoutTest(test_gui.GuiTest):
    def test_small_max_text_keeps_title_editor_and_result_separate(self):
        self.boot()
        self.make_round("r90", [self.first(kind="code", type="fill")])
        self.win.open_round("r90")
        self.idle()
        page = self.win.round_page
        editor, console = page.code_panel.editor, page.code_panel.console
        answer = "\n".join("value = %d" % number for number in range(30))
        editor.setPlainText(answer)
        page.flush()
        cursor = editor.textCursor()
        cursor.setPosition(0)
        cursor.setPosition(5, QTextCursor.MoveMode.KeepAnchor)
        editor.setTextCursor(cursor)
        changed = QSignalSpy(page.code_panel.changed)
        self.addCleanup(theme.set_mode, theme.state["mode"])
        room = self.win.screen().availableGeometry()
        native = guikit.APP.platformName() == "windows"
        wide_size = (min(1440, room.width() - 32), min(900, room.height() - 64)) if native else (1440, 900)
        if native:
            self.win.move(room.topLeft() + QPoint(16, 32))
        samples = []

        def record_geometry():
            destination = os.environ.get("STUDY_UI_ARTIFACT_DIR")
            if destination:
                path = Path(destination) / "round-window-geometry.json"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps({"platform": guikit.APP.platformName(), "device_pixel_ratio": self.win.devicePixelRatioF(),
                                            "screen_available": list(room.getRect()), "requested_wide": [1440, 900],
                                            "tested_wide": wide_size, "samples": samples}, ensure_ascii=False, indent=2), encoding="utf-8")

        def resize_settled(size, stage):
            self.win.resize(*size)
            previous, stable = None, 0
            def settled():
                nonlocal previous, stable
                current = (self.win.size(), page.size(), page.split.size(), tuple(page.split.sizes()), page.bar.geometry(),
                           page.item_title.geometry(), page.body.geometry(), editor.geometry(), console.geometry())
                if current != previous:
                    samples.append({"stage": stage, "requested": list(size),
                                    "window": [self.win.width(), self.win.height()], "splitter": [page.split.width(), page.split.height()],
                                    "sizes": page.split.sizes(), "frame": list(self.win.frameGeometry().getRect()),
                                    "title": list(page.item_title.geometry().getRect()), "editor": list(editor.geometry().getRect()),
                                    "console": list(console.geometry().getRect())})
                stable = stable + 1 if current == previous else 0
                previous = current
                return ((self.win.width(), self.win.height()) == size and page.width() == self.win.width()
                        and page.split.width() == page.width() and stable >= 3)
            try:
                guikit.wait_until(settled, timeout=3)
            finally:
                record_geometry()
            if native:
                self.assertTrue(room.contains(self.win.frameGeometry()), samples[-1])

        for mode in ("light", "dark"):
            with self.subTest(mode=mode):
                theme.set_mode(mode)
                self.win.set_text("larger")
                resize_settled(wide_size, mode + "-wide-before")
                wide = page.split.sizes()
                resize_settled((760, 480), mode + "-small")
                self.assertEqual(page.bar.height(), theme.CONTROL["bottombar_dense"])
                self.assertEqual(page.listw.width(), 160)
                self.assertEqual((self.win.width(), self.win.height()), (760, 480))
                self.assertGreaterEqual(page.item_title.height(), page.item_title.heightForWidth(page.item_title.width()))
                self.assertGreaterEqual(page.body.height(), 150)
                self.assertGreaterEqual(editor.height(), 70)
                self.assertGreaterEqual(console.height(), 50)
                self.assertFalse(editor.geometry().intersects(console.geometry()))
                self.assertLess(editor.geometry().bottom(), console.geometry().top())
                for widget in (editor, console):
                    self.assertTrue(widget.parentWidget().rect().contains(widget.geometry()))
                for button in (page.run_btn, page.prev_btn, page.next_btn, page.submit_btn):
                    self.assertTrue(page.rect().contains(button.rect().translated(button.mapTo(page, QPoint(0, 0)))))
                resize_settled(wide_size, mode + "-wide-after")
                for actual, expected in zip(page.split.sizes(), wide):
                    self.assertLessEqual(abs(actual - expected), 1, samples[-1])
                self.assertEqual(editor.toPlainText(), answer)
                self.assertEqual(editor.textCursor().selectedText(), "value")
                self.assertEqual(page.current["answer"], answer)
                self.assertEqual(len(changed), 0)
                self.assertFalse(page.save_timer.isActive())

        resize_settled((760, 480), "capture-small")
        self.capture_widget = self.win

    def test_first_wide_window_splits_panes_by_the_wide_sizes(self):
        """처음 연 넓은 창은 목록 240, 지문과 답안을 480:488 로 나눔. 숨은 페이지의 처음 크기 비율이 남지 않음."""
        self.boot()
        self.make_round("r90", [self.first(kind="code", type="fill")])
        page = self.win.round_page
        middle, right = round_page.WIDE_SIZES[1:]
        for size in ((1280, 800), (1920, 1080)):
            with self.subTest(size=size):
                self.win.resize(*size)
                self.win.open_round("r90")
                self.idle()
                guikit.wait_until(lambda: page.split.width() == page.width() and not page.compact, timeout=3)
                sizes = page.split.sizes()
                self.assertEqual(sizes[0], round_page.WIDE_SIZES[0])
                self.assertLessEqual(abs(sizes[1] - round((sizes[1] + sizes[2]) * middle / (middle + right))), 1, sizes)
                if size == (1280, 800):
                    self.assertEqual(sizes, round_page.WIDE_SIZES)
                self.win.go_home()
                self.idle()

    def test_body_code_box_does_not_scroll_sideways_at_the_largest_step(self):
        """지문 코드 상자의 안 여백 때문에 가장 큰 글자에서 지문 칸에 가로 스크롤이 새로 생기지 않음.
        s01/p03 은 760×480, s09/p13 은 1024×700 에서 코드 상자 좌우 여백을 16 으로 늘리면 가로 스크롤이 생기던 문항임."""
        self.boot()
        keys = {"s01/p03": (760, 480), "s09/p13": (1024, 700)}
        for key in keys:
            self.assertEqual(self.win.session.cat[key]["kind"], "code")
        self.make_round("r90", list(keys))
        self.win.open_round("r90")
        self.idle()
        page = self.win.round_page
        self.addCleanup(theme.set_text, theme.state["text"])
        self.win.set_text("larger")
        for row, (key, size) in enumerate(keys.items()):
            with self.subTest(key=key, size=size):
                self.win.resize(*size)
                guikit.wait_until(lambda: (self.win.width(), self.win.height()) == size, timeout=3)
                page.listw.setCurrentRow(row)
                self.idle()
                self.assertIn("codebox", page.body_html(page.current))
                self.assertEqual(page.body.horizontalScrollBar().maximum(), 0)
