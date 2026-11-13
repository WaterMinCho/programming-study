"""매거진의 표지와 실제 재생창 사이의 재시도·외부 이동을 확인함."""
from unittest.mock import Mock, patch

from tests import guikit
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QWidget

from gui.video_viewer import EngineUnavailable
from tests.test_gui_hub import HubTest


class GalleryPlaybackTest(HubTest):
    def test_double_click_hands_video_to_browser_once(self):
        win = self.boot()
        win.open_url = Mock(return_value=True)
        win.go_magazine()
        page = win.career.magazine
        video = next(v for v in page.catalog.videos if v.embeddable is not False)
        cover = page.rows[video.video_id].cover
        with patch("gui.video_viewer.create_engine", side_effect=EngineUnavailable("재생기 미설치")) as factory:
            QTest.mouseClick(cover, guikit.LEFT)
            QTest.mouseDClick(cover, guikit.LEFT)
            QTest.mouseRelease(cover, guikit.LEFT)
            win.open_url.assert_called_once_with("https://www.youtube.com/watch?v=" + video.video_id)
            factory.assert_called_once()
            self.assertIsNone(win.career.video)
            QTest.mouseClick(cover, guikit.LEFT)
            self.assertEqual(win.open_url.call_count, 2)

    def test_player_retry_hides_error_on_the_same_card(self):
        class Engine:
            def __init__(self, parent, event, open_url):
                self.widget = QWidget(parent)
                self.event = event

            def start(self, video_id):
                self.event("ready")

            def close(self):
                self.widget.deleteLater()

        win = self.boot()
        win.go_magazine()
        page = win.career.magazine
        with patch("gui.video_viewer.create_engine", Engine):
            page.play_video()
            dialog = win.career.video
            dialog.engine.event("state", 1)
            dialog.engine.event("error", 101)
            card = page.rows[page.selected_video_id]
            self.assertTrue(card.error.isVisible())
            self.assertEqual(card.error.text(), dialog.status.text())
            guikit.click(dialog.retry_button)
            dialog.engine.event("state", 1)
            self.assertEqual(page.playback_state, "playing")
            self.assertFalse(card.error.isVisible())
            dialog.close()
