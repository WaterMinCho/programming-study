"""임시 화면에서 선택·재생 요청·그림 배치와 읽던 위치를 확인함."""
from dataclasses import replace
from pathlib import Path
import os
import tempfile
import unittest
from unittest.mock import Mock, patch

from tests import guikit
from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QFontMetricsF, QImageReader
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QLabel, QPushButton, QWidget

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
        if isinstance(window, CareerRoadmapPage) and window.role_picker.currentData():
            window.select_role(window.role_picker.currentData())
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

    def _sizes(self, widget):
        sizes = ((760, 480), (1024, 700), (1280, 800))
        if os.name != "nt":
            return sizes
        room = widget.screen().availableGeometry()
        tested = tuple((min(w, room.width() - 32), min(h, room.height() - 64)) for w, h in sizes)
        destination = os.environ.get("CAREER_EVIDENCE")
        if destination:
            import json
            data = {"requested": sizes, "tested": tested, "available": [room.width(), room.height()],
                    "scope": "Large native windows fit the actual runner work area. Full requested sizes remain in offscreen cases; small 760x480 unchanged."}
            Path(destination).mkdir(parents=True, exist_ok=True)
            (Path(destination) / "career-window-sizes.json").write_text(json.dumps(data, indent=2))
        widget.move(room.topLeft() + QPoint(16, 32))
        return tested

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

    def test_role_scenes_pair_on_wide_windows_and_switch_on_small_windows(self):
        saved = Mock()
        page = self.show(CareerRoadmapPage, on_select_goal=saved)
        scene = page.scene
        for role in self.catalog.roles:
            page.select_role(role["id"])
            self.assertFalse(scene.picture.pixmap.isNull(), role["id"])
            self.assertTrue(scene.picture.accessibleDescription())
        page.select_role("robot_navigation")
        self.assertTrue(scene.tabs.isVisible())
        guikit.click(scene.tabs.buttons[1])
        self.assertTrue(scene.artifact.isVisible())
        self.assertFalse(scene.picture.isVisible())
        self.assertEqual(scene.caption.text(), scene.artifact.accessibleDescription())
        page.resize(1350, 800)
        self.settle(page)
        self.assertTrue(scene.picture.isVisible() and scene.artifact.isVisible())
        self.assertTrue(scene.tabs.isHidden())
        self.assertEqual(scene.picture.mapTo(page, QPoint()).y(), scene.artifact.mapTo(page, QPoint()).y())
        self.assertEqual(scene.picture.height(), scene.artifact.height())
        page.resize(760, 480)
        self.settle(page)
        self.assertTrue(scene.artifact.isVisible())
        self.assertTrue(page.filters.isHidden())
        page.show_catalog()
        guikit.click(page.filter_toggle)
        self.assertTrue(page.filters.isVisible())
        saved.assert_not_called()

    def test_missing_scene_shows_the_result_and_next_role_restores_preferred_view(self):
        page = self.show(CareerRoadmapPage)
        with tempfile.TemporaryDirectory() as directory, patch("gui.career_scene.SCENES", Path(directory)):
            page.select_role("frontend")
            self.assertTrue(page.scene.tabs.isHidden())
            self.assertTrue(page.scene.artifact.isVisible())
        page.select_role("robot_vision")
        self.assertTrue(page.scene.picture.isVisible())
        self.assertTrue(page.scene.tabs.isVisible())

    def test_roadmap_sources_and_related_videos_open_selected_targets(self):
        source, video, magazine = Mock(), Mock(), Mock()
        page = self.show(CareerRoadmapPage, on_source=source, on_video=video, on_magazine=magazine)
        page.select_role("frontend")
        self.settle(page)
        source.assert_not_called()
        role = self.catalog.role("frontend")
        expected = [row for row in self.catalog.sources if row["id"] in role["source_ids"]]
        self.assertTrue(page.source_box.isHidden())
        guikit.click(page.sources_button)
        links = page.source_box.findChildren(QPushButton)
        self.assertEqual(len(links), len(expected))
        for link, row in zip(links, expected):
            self.assertEqual(link.toolTip(), row["url"])
            guikit.click(link)
            source.assert_called_with(row["url"])
        buttons = {button.text(): button for button in page.findChildren(QPushButton)}
        for label, key in (("로봇 개발자의 업무", "H89Az-iZZrc"), ("로봇 개발 프로젝트 준비", "HCx2ICUe0eA")):
            guikit.click(buttons[label])
            video.assert_called_with(key)
        guikit.click(buttons["매거진 열기"])
        magazine.assert_called_once()
        self.assertEqual(page.selected_role_id, "frontend")

    def test_external_video_work_only_follows_explicit_play_and_stop(self):
        play, stop, source = Mock(), Mock(), Mock()
        with patch("socket.socket", side_effect=AssertionError("네트워크 사용")):
            page = self.show(CareerMagazinePage, on_video=play, on_stop=stop, on_source=source)
            other = self.catalog.videos[1].video_id
            page.select_video(other)
            play.assert_not_called()
            stop.assert_not_called()
            self.assertEqual(page.playback_state, "idle")
            guikit.click(page.rows[other].cover)
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
        self.assertFalse(any(card.cover.isEnabled() for card in page.rows.values()))
        self.assertIn("오프라인", page.network_note.text())
        page.play_video()
        callback.assert_called_once()
        self.assertEqual(len(page.rows), 38)

    def test_playback_error_shows_player_detail_or_default_once(self):
        page = self.show(CareerMagazinePage, on_video=Mock(), on_stop=Mock())
        video_id = page.selected_video_id
        default = "영상을 재생하지 못했습니다. YouTube 원본에서 확인해 주세요."
        detail = "게시자가 외부 재생을 제한했습니다."
        for message, expected in ((detail, detail), ("", default), ("  ", default)):
            with self.subTest(message=message):
                page.play_video()
                self.assertTrue(page.set_playback_state(video_id, "error", message))
                self.assertEqual(page.rows[video_id].error.text(), expected)
                self.assertEqual(page.playback_note.text(), expected)

    def test_search_preserves_preview_and_lists_are_sorted(self):
        page = self.show(CareerMagazinePage)
        selected = page.selected_video_id
        self.assertEqual(list(page.rows), [row.video_id for row in self.catalog.videos])
        page.search.setText("찾을수없는임시검색")
        self.assertEqual(page.rows, {})
        self.assertEqual(page.selected_video_id, selected)
        self.assertTrue(page.empty_note.isVisible())
        self.assertIn("검색 조건", page.empty_note.text())
        page.search.clear()
        page.origin.setCurrentIndex(1)
        self.assertEqual(len(page.rows), 18)

    def test_empty_unavailable_invalid_and_paper_states_are_distinct(self):
        for state, expected in (("empty", "공개한 영상"), ("unavailable", "파일이 없습니다"), ("invalid", "읽지 못")):
            catalog = Catalog(states={"roles": state, "videos": state, "papers": state})
            page = self.show(CareerMagazinePage, catalog=catalog)
            self.assertIn(expected, page.empty_note.text())
            self.assertFalse(page.play_button.isEnabled())
        paper = Paper("fixture", "임시 논문", "https://example.org/paper", None, "임시 요약입니다.", "임시 설명입니다.", "2026-11-14")
        catalog = replace(self.catalog, papers=(paper,), states={**self.catalog.states, "papers": "ready"})
        callback = Mock()
        page = self.show(CareerMagazinePage, catalog=catalog, on_paper=callback)
        page.tabs.picked.emit(1)
        page.open_paper(paper)
        callback.assert_called_once_with(paper)

    def test_cover_activates_once_and_information_returns_to_its_card(self):
        play, stop, source = Mock(), Mock(), Mock()
        page = self.show(CareerMagazinePage, on_video=play, on_stop=stop, on_source=source)
        page.origin.setCurrentIndex(1)
        page.search.setText("로봇")
        self.settle(page)
        card = list(page.rows.values())[-1]
        video = card.cover.video
        page.scroll.ensureWidgetVisible(card.info)
        card.info.setFocus()
        self.settle(page)
        bar = page.scroll.verticalScrollBar()
        before = bar.value()
        selected = page.selected_video_id
        self.assertGreater(before, 0)
        QTest.keyClick(card.info, Qt.Key.Key_Space)
        guikit.pump()
        dialog = page.info_dialog
        self.assertTrue(dialog.isVisible())
        shown = [label.text() for label in dialog.findChildren(QLabel)]
        for text in (video.title, video.summary, video.learning_use, video.limitations):
            self.assertIn(text, shown)
        buttons = {button.toolTip(): button for button in dialog.findChildren(QPushButton)}
        guikit.click(buttons[video.url])
        source.assert_called_once_with(video.url)
        QTest.keyClick(dialog, Qt.Key.Key_Escape)
        self.settle(page)
        self.assertIsNone(page.info_dialog)
        self.assertIs(page.focusWidget(), card.info)
        self.assertEqual(bar.value(), before)
        self.assertEqual(page.selected_video_id, selected)
        self.assertEqual(page.search.text(), "로봇")
        self.assertEqual(page.origin.currentData(), "selected")
        play.assert_not_called()

        card.cover.setFocus()
        self.settle(page)
        before = bar.value()
        play.side_effect = lambda item: self.assertEqual(page.selected_video_id, item.video_id)
        for key in (Qt.Key.Key_Return, Qt.Key.Key_Space, Qt.Key.Key_Enter):
            with self.subTest(key=key):
                QTest.keyClick(card.cover, key)
                self.settle(page)
                play.assert_called_once_with(video)
                self.assertEqual(bar.value(), before)
                self.assertTrue(page.set_playback_state(video.video_id, "ended"))
                play.reset_mock()
        stop.assert_not_called()

    def test_related_cover_outside_filters_is_visible_and_plays_only_on_activation(self):
        play = Mock()
        page = self.show(CareerMagazinePage, on_video=play, on_stop=Mock())
        page.origin.setCurrentIndex(page.origin.findData("additional"))
        page.search.setText("kakao")
        matches = list(page.rows)
        targets = ["H89Az-iZZrc", "HCx2ICUe0eA"]
        self.assertTrue(matches)
        for target in targets:
            self.assertNotIn(target, matches)
            self.assertTrue(page.select_video(target, reveal=True))
            self.settle(page)
            card = page.rows[target]
            self.assertEqual(list(page.rows), [target, *matches])
            self.assertTrue(card.related_note.isVisible())
            self.assertIs(page.focusWidget(), card.cover)
            viewport = page.scroll.viewport()
            self.assertTrue(viewport.rect().contains(card.cover.rect().translated(card.cover.mapTo(viewport, QPoint()))))
            self.assertEqual(page.search.text(), "kakao")
            self.assertEqual(page.origin.currentData(), "additional")
            self.assertIsNone(page.info_dialog)
            play.assert_not_called()
        QTest.keyClick(card.cover, Qt.Key.Key_Return)
        play.assert_called_once_with(card.cover.video)
        page.search.setText("kakao tech")
        self.assertNotIn(target, page.rows)
        self.assertEqual(page.selected_video_id, target)
        self.assertFalse(card.related_note.isVisible())
        page.search.setText("검색 결과가 없는 제목")
        self.assertFalse(page.rows)
        self.assertTrue(page.select_video(target, reveal=True))
        self.settle(page)
        self.assertEqual(list(page.rows), [target])
        self.assertFalse(page.empty_note.isVisible())
        self.assertIs(page.focusWidget(), card.cover)
        play.assert_called_once()

    def test_related_cover_already_in_results_scrolls_to_target_in_catalog_order(self):
        play = Mock()
        page = self.show(CareerMagazinePage, on_video=play, on_stop=Mock())
        ordered = list(page.rows)
        card = page.rows[ordered[-3]]
        page.select_video(card.cover.video.video_id, reveal=True)
        self.settle(page)
        viewport = page.scroll.viewport()
        self.assertTrue(viewport.rect().contains(card.cover.rect().translated(card.cover.mapTo(viewport, QPoint()))))
        self.assertIs(page.focusWidget(), card.cover)
        self.assertEqual(list(page.rows), ordered)
        self.assertFalse(card.related_note.isVisible())
        play.assert_not_called()

    def test_first_cover_is_highlighted_only_after_selection_or_play(self):
        play = Mock()
        page = self.show(CareerMagazinePage, on_video=play, on_stop=Mock())
        first = self.catalog.videos[0]
        self.assertEqual(page.video(), first)
        self.assertFalse(any(card.cover.isChecked() for card in page.rows.values()))
        play.assert_not_called()
        page.play_video()
        play.assert_called_once_with(first)
        self.assertTrue(page.rows[first.video_id].cover.isChecked())

    def test_shipped_webp_decodes_and_missing_or_invalid_cover_still_plays(self):
        from gui.career_gallery import COVERS
        ids = {video.video_id for video in self.catalog.videos}
        self.assertEqual(len(ids), 38)
        self.assertEqual(ids, {path.stem for path in COVERS.glob("*.webp")})
        self.assertIn(b"webp", QImageReader.supportedImageFormats())
        for video in self.catalog.videos:
            reader = QImageReader(str(COVERS / (video.video_id + ".webp")))
            self.assertEqual(bytes(reader.format()), b"webp", video.video_id)
            image = reader.read()
            self.assertFalse(image.isNull(), (video.video_id, reader.errorString()))
            self.assertEqual(image.width() * 9, image.height() * 16)
        videos = self.catalog.videos[:2]
        play = Mock()
        with tempfile.TemporaryDirectory() as folder, patch("gui.career_gallery.COVERS", Path(folder)):
            (Path(folder) / (videos[1].video_id + ".webp")).write_bytes(b"invalid")
            with patch("socket.socket", side_effect=AssertionError("네트워크 사용")):
                page = self.show(CareerMagazinePage, catalog=replace(self.catalog, videos=videos),
                                 on_video=play, on_stop=Mock())
                for video in videos:
                    cover = page.rows[video.video_id].cover
                    self.assertFalse(cover.grab().isNull())
                    self.assertTrue(cover.image.isNull())
                    guikit.click(cover)
                    play.assert_called_once_with(video)
                    play.reset_mock()

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
        guikit.click(page.team_toggle)
        for scheme in ("light", "dark"):
            theme.set_mode(scheme)
            theme.set_text("larger")
            kit.refont(page)
            for width, height in self._sizes(page):
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
            for width, height in self._sizes(page):
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

                    self._capture(page, f"magazine-{scheme}-{width}x{height}" + ("-paper" if tab else ""))
        self.capture_widget = page

    def test_gallery_columns_cover_alignment_and_filter_wrapping(self):
        page = self.show(CareerMagazinePage, on_video=Mock(), on_stop=Mock())
        for width, font, columns in ((480, "larger", 1), (760, "larger", 2), (1000, "normal", 3),
                                     (1000, "larger", 2), (1280, "larger", 3)):
            with self.subTest(width=width, font=font):
                theme.set_text(font)
                kit.refont(page)
                page.resize(width, 700)
                self.settle(page)
                self.assertEqual(page.gallery.columns, columns)
                cards = list(page.rows.values())
                for i, card in enumerate(cards):
                    self.assertEqual(card.cover.height(), round(card.cover.width() * 9 / 16))
                    first = cards[i - i % columns]
                    self.assertEqual(card.y(), first.y())
                    self.assertLessEqual(abs(card.cover.width() - first.cover.width()), 1)
                    self.assertEqual(card.author.mapTo(page.gallery, QPoint()).y(),
                                     first.author.mapTo(page.gallery, QPoint()).y())
                    self.assertGreaterEqual(card.title.height(), card.title.heightForWidth(card.title.width()))
        page.resize(380, 620)
        self.settle(page)
        self.assertGreater(page.origin.y(), page.search.y())
        self.assertLessEqual(page.content.width(), page.width())

    def test_gallery_reflow_keeps_reading_card_across_column_changes(self):
        page = self.show(CareerMagazinePage)
        page.resize(1280, 800)
        self.settle(page)
        page.scroll.verticalScrollBar().setValue(1800)
        card, offset = page._anchor
        for width, size in ((760, "larger"), (480, "larger"), (1280, "normal")):
            theme.set_text(size)
            kit.refont(page)
            page.resize(width, 800)
            self.settle(page)
            self.assertLessEqual(abs(card.mapTo(page.scroll.viewport(), QPoint()).y() - offset), 1)

    def test_existing_image_viewer_and_missing_image_preserve_role(self):
        page = self.show(CareerRoadmapPage)
        self.assertEqual(page.image_button.text(), "학습 로드맵 크게 보기")
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
            self.assertTrue(dialog.isMaximized())
            room = page.window().screen().availableGeometry()
            self.assertIs(dialog.screen(), page.window().screen())
            self.assertGreater(dialog.width(), room.width() * 0.9)
            self.assertGreater(dialog.height(), room.height() * 0.85)
            view = dialog.area
            original = view.original
            self.assertFalse(original.isNull())
            self.assertGreater(view.viewport().height(), dialog.height() * 0.64)
            self.assertEqual(view.horizontalScrollBar().maximum(), 0)
            self.assertAlmostEqual(view.scale * original.width(), view.viewport().width(), delta=1)
            before, key = original.size(), original.cacheKey()
            guikit.click(dialog.more)
            self.assertGreater(view.scale * original.width(), view.viewport().width())
            self.assertEqual((view.original.size(), view.original.cacheKey()), (before, key))
            guikit.click(dialog.fit)
            view.verticalScrollBar().setValue(view.verticalScrollBar().maximum() // 2)
            guikit.pump()
            for button in (dialog.less, dialog.more, dialog.fit, dialog.window_size, dialog.close_button):
                top = button.mapTo(dialog, QPoint(0, 0))
                self.assertGreaterEqual(top.y(), 0)
                self.assertLessEqual(top.y() + button.height(), dialog.height())
                self.assertGreaterEqual(button.width(), QFontMetricsF(button.font()).horizontalAdvance(button.text()))
            if palette == "light":
                guikit.click(dialog.close_button)
                self.assertIsNone(page.image_dialog)
            else:
                self.capture_widget = dialog


if __name__ == "__main__":
    unittest.main()
