"""임시 화면에서 선택·재생 요청·그림 배치와 읽던 위치를 확인함."""
from dataclasses import replace
from pathlib import Path
import os
import tempfile
import unittest
from unittest.mock import Mock, patch

from tests import guikit
from PyQt6.QtCore import QPoint
from PyQt6.QtGui import QFontMetricsF
from PyQt6.QtWidgets import QPushButton, QWidget

from career.catalog import Catalog, Paper, load_catalog
from gui import kit, theme
from gui.career_magazine import CareerMagazinePage
from gui.career_roadmap import CareerFlow, CareerRoadmapPage


class CareerGuiTest(unittest.TestCase):
    def setUp(self):
        self.catalog = load_catalog()
        self.windows = []
        self.theme_state = dict(theme.state)

    def tearDown(self):
        for window in self.windows:
            window.close()
            window.deleteLater()
        guikit.pump()
        theme.set_text(self.theme_state["text"])
        theme.set_mode(self.theme_state["mode"])

    def show(self, cls, **kwargs):
        window = cls(catalog=kwargs.pop("catalog", self.catalog), **kwargs)
        self.windows.append(window)
        window.resize(760, 480)
        window.show()
        self.settle(window)
        return window

    def settle(self, window):
        previous = None
        stable = 0
        for _ in range(60):
            guikit.pump(5)
            current = (window.content.size(), window.scroll.verticalScrollBar().maximum(),
                       tuple((child.size(), child.pos()) for child in window.content.findChildren(CareerFlow)))
            stable = stable + 1 if current == previous else 0
            previous = current
            if stable >= 3 and not window._settling:
                return
        self.fail("화면 배치가 안정되지 않았음")

    def _capture(self, widget, name):
        destination = os.environ.get("CAREER_EVIDENCE")
        if destination:
            target = Path(destination)
            target.mkdir(parents=True, exist_ok=True)
            self.assertTrue(widget.grab().save(str(target / (name + ".png"))))
            if os.name == "nt":
                self.assertTrue(widget.screen().grabWindow(int(widget.winId())).save(str(target / (name + "-native.png"))))

    def test_browse_does_not_save_and_explicit_goal_has_both_ids(self):
        callback = Mock()
        page = self.show(CareerRoadmapPage, on_select_goal=callback)
        self.assertTrue(page.select_role("frontend"))
        callback.assert_not_called()
        self.assertIn("일부 공통 기술", page.relation.text())
        guikit.click(page.goal_button)
        callback.assert_called_once_with("frontend", "platform")
        self.assertFalse(page.select_role("missing"))

    def test_filters_and_empty_results_keep_valid_selection(self):
        page = self.show(CareerRoadmapPage)
        page.industry.setCurrentIndex(page.industry.findData("mobility"))
        self.assertEqual(page.role_picker.count(), 2)
        page.select_role("qa")
        self.assertEqual(page.selected_role_id, "qa")
        self.assertEqual(page.role_picker.currentData(), "qa")

    def test_external_video_work_only_follows_explicit_play_and_stop(self):
        play, stop, source = Mock(), Mock(), Mock()
        with patch("socket.socket", side_effect=AssertionError("네트워크 사용")):
            page = self.show(CareerMagazinePage, on_video=play, on_stop=stop, on_source=source)
            other = self.catalog.videos[1].video_id
            page.select_video(other)
            play.assert_not_called()
            stop.assert_not_called()
            self.assertEqual(page.playback_state, "idle")
            guikit.click(page.play_button)
            self.assertEqual(play.call_args[0][0].video_id, other)
            self.assertEqual(page.playback_state, "requested")
            self.assertNotIn("재생하고", page.playback_note.text())
            page.play_video()
            play.assert_called_once()
            self.assertFalse(page.set_playback_state("old_video__", "playing"))
            self.assertTrue(page.set_playback_state(other, "playing"))
            page.select_video(self.catalog.videos[0].video_id)
            stop.assert_called_once()
            self.assertFalse(page.set_playback_state(other, "playing"))
            page.play_video()
            page.tabs.picked.emit(1)
            self.assertEqual(stop.call_count, 2)
            page.tabs.picked.emit(0)
            source.assert_not_called()

    def test_host_injection_does_not_start_playback_and_hide_stops_once(self):
        play, stop = Mock(), Mock()
        page = self.show(CareerMagazinePage, on_video=play, on_stop=stop)
        viewer = QWidget()
        page.set_viewer(viewer)
        self.assertIs(viewer.parentWidget(), page.viewer_host)
        play.assert_not_called()
        page.play_video()
        page.hide()
        guikit.pump()
        stop.assert_called_once()
        page.stop_playback()
        stop.assert_called_once()

    def test_callback_failure_and_offline_do_not_claim_playback(self):
        callback = Mock(side_effect=RuntimeError("임시 오류"))
        page = self.show(CareerMagazinePage, on_video=callback, on_stop=Mock())
        page.play_video()
        self.assertEqual(page.playback_state, "error")
        self.assertIn("열지 못", page.playback_note.text())
        page.set_online(False)
        self.assertFalse(page.play_button.isEnabled())
        self.assertIn("오프라인", page.network_note.text())
        page.play_video()
        callback.assert_called_once()
        self.assertEqual(len(page.rows), 38)

    def test_search_preserves_preview_and_lists_are_sorted(self):
        page = self.show(CareerMagazinePage)
        selected = page.selected_video_id
        self.assertEqual(list(page.rows), [row.video_id for row in self.catalog.videos])
        page.search.setText("찾을수없는임시검색")
        self.assertEqual(page.rows, {})
        self.assertEqual(page.selected_video_id, selected)
        self.assertTrue(page.detail.isVisible())
        page.search.clear()
        page.origin.setCurrentIndex(1)
        self.assertEqual(len(page.rows), 18)

    def test_empty_unavailable_invalid_and_paper_states_are_distinct(self):
        for state, expected in (("empty", "공개한 영상"), ("unavailable", "파일이 없습니다"), ("invalid", "읽지 못")):
            catalog = Catalog(states={"roles": state, "videos": state, "papers": state})
            page = self.show(CareerMagazinePage, catalog=catalog)
            self.assertIn(expected, page.rows_layout.itemAt(0).widget().text())
            self.assertFalse(page.play_button.isEnabled())
        paper = Paper("fixture", "임시 논문", "https://example.org/paper", None, "임시 요약입니다.", "임시 설명입니다.", "2026-11-14")
        catalog = replace(self.catalog, papers=(paper,), states={**self.catalog.states, "papers": "ready"})
        callback = Mock()
        page = self.show(CareerMagazinePage, catalog=catalog, on_paper=callback)
        page.tabs.picked.emit(1)
        page.open_paper(paper)
        callback.assert_called_once_with(paper)

    def test_paper_figure_callback_receives_original_design_and_review_scope(self):
        figure, source = Mock(), Mock()
        page = self.show(CareerMagazinePage, on_figure=figure, on_source=source)
        paper = self.catalog.papers[0]
        figure.assert_not_called()
        page.open_figure(paper)
        figure.assert_called_once_with(paper)
        self.assertTrue(paper.verification_scope)
        self.assertEqual(len(paper.figure_description), 4)
        source.assert_not_called()

    def test_magazine_tabs_restore_reading_position_and_selected_video(self):
        page = self.show(CareerMagazinePage)
        page.select_video("H89Az-iZZrc", reveal=False)
        self.settle(page)
        bar = page.scroll.verticalScrollBar()
        bar.setValue(2000)
        page._remember()
        before = bar.value()
        page.tabs.picked.emit(1)
        self.settle(page)
        page.tabs.picked.emit(0)
        self.settle(page)
        self.assertEqual(page.selected_video_id, "H89Az-iZZrc")
        self.assertEqual(bar.value(), before)

    def test_font_theme_and_page_roundtrip_keep_selection_and_reading_anchor(self):
        page = self.show(CareerRoadmapPage)
        page.select_role("robot_policy")
        self.settle(page)
        bar = page.scroll.verticalScrollBar()
        bar.setValue(min(1600, bar.maximum()))
        guikit.pump()
        page._remember()
        child, offset = page._anchor
        theme.set_text("larger")
        kit.refont(page)
        theme.set_mode("dark")
        self.settle(page)
        self.assertEqual(page.selected_role_id, "robot_policy")
        self.assertLessEqual(abs(child.mapTo(page.scroll.viewport(), QPoint()).y() - offset), 1)
        before = bar.value()
        page.hide()
        page.show()
        self.settle(page)
        self.assertEqual(bar.value(), before)

    def test_small_windows_themes_fonts_and_flow_bounds(self):
        page = self.show(CareerRoadmapPage, on_select_goal=Mock(), on_back=Mock())
        for scheme in ("light", "dark"):
            theme.set_mode(scheme)
            theme.set_text("larger")
            kit.refont(page)
            for width, height in ((760, 480), (1024, 700), (1280, 800)):
                page.resize(width, height)
                self.settle(page)
                self.assertEqual(page.width(), width)
                self.assertLessEqual(page.content.width(), width)
                self.assertLess(page.top.back.width(), page.width() // 2)
                self.assertEqual(page.top.back.x(), kit.MARGIN - kit.FLUSH)
                for role in self.catalog.roles:
                    page.select_role(role["id"])
                    self.settle(page)
                    for diagram in (page.context_flow, page.work_flow):
                        diagram.grab()
                        self.assertGreaterEqual(diagram.height(), diagram.heightForWidth(diagram.width()) - 1)
                        for rect in diagram.node_rects + diagram.text_rects:
                            self.assertGreaterEqual(rect.left(), 0)
                            self.assertLessEqual(rect.right(), diagram.width() + 1)
                            self.assertLessEqual(rect.bottom(), diagram.height() + 1)
                for button in page.findChildren(QPushButton):
                    if button.isVisibleTo(page):
                        self.assertGreaterEqual(button.width(), QFontMetricsF(button.font()).horizontalAdvance(button.text()))

                self._capture(page, f"roadmap-{scheme}-{width}x{height}")
        self.capture_widget = page

    def test_magazine_small_windows_keep_text_and_actions_inside_content(self):
        page = self.show(CareerMagazinePage, on_back=Mock(), on_video=Mock(), on_stop=Mock(), on_paper=Mock(),
                         on_source=Mock(), on_figure=Mock())
        for scheme in ("light", "dark"):
            theme.set_mode(scheme)
            theme.set_text("larger")
            kit.refont(page)
            for width, height in ((760, 480), (1024, 700), (1280, 800)):
                page.resize(width, height)
                for tab in (0, 1):
                    page.tabs.picked.emit(tab)
                    self.settle(page)
                    self.assertEqual(page.width(), width)
                    self.assertLessEqual(page.content.width(), width)
                    for child in page.content.findChildren(QWidget):
                        if child.isVisibleTo(page.content):
                            x = child.mapTo(page.content, QPoint()).x()
                            self.assertGreaterEqual(x, -1)
                            self.assertLessEqual(x + child.width(), page.content.width() + 1)
                    for button in page.findChildren(QPushButton):
                        if button.isVisibleTo(page):
                            self.assertGreaterEqual(button.width(), QFontMetricsF(button.font()).horizontalAdvance(button.text()))

                self._capture(page, f"magazine-{scheme}-{width}x{height}")
        self.capture_widget = page

    def test_existing_image_viewer_and_missing_image_preserve_role(self):
        page = self.show(CareerRoadmapPage)
        repository = page.repository
        with tempfile.TemporaryDirectory() as directory:
            page.repository = Path(directory)
            selected = page.selected_role_id
            page.open_image()
            self.assertIn("읽지 못", page.image_notice.text())
            self.assertEqual(page.selected_role_id, selected)
        page.repository = repository
        theme.set_text("larger")
        for palette in ("light", "dark"):
            theme.set_mode(palette)
            kit.refont(page)
            page.resize(760, 480)
            guikit.pump()
            page.open_image()
            guikit.pump()
            dialog = page.image_dialog
            self.windows.append(dialog)
            self.assertFalse(dialog.original.isNull())
            self.assertLessEqual(dialog.width(), page.width())
            self.assertLessEqual(dialog.height(), page.height())
            before = dialog.original.size()
            dialog.zoom(1.25)
            self.assertEqual(dialog.original.size(), before)
            self.assertGreater(dialog.image.width(), before.width())
            for button in (dialog.less, dialog.more, dialog.fit, dialog.close_button):
                top = button.mapTo(dialog, QPoint(0, 0))
                self.assertGreaterEqual(top.y(), 0)
                self.assertLessEqual(top.y() + button.height(), dialog.height())
                self.assertGreaterEqual(button.width(), QFontMetricsF(button.font()).horizontalAdvance(button.text()))
            if palette == "light":
                dialog.close()
            else:
                self.capture_widget = dialog


if __name__ == "__main__":
    unittest.main()
