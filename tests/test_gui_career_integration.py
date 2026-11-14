"""커리어 진입과 기존 학습·목표 기록의 경계를 임시 기기에서 확인함."""
import json
import unittest
import threading
import os
import sys
from pathlib import Path
from unittest import mock

from tests import guikit
from tests.test_gui_hub import HubTest
from gui import theme


class CareerIntegrationTest(unittest.TestCase):
    setUp = HubTest.setUp
    tearDown = HubTest.tearDown
    boot = HubTest.boot
    idle = HubTest.idle

    def test_career_is_lazy_and_selection_does_not_reclassify_learning_records(self):
        win = self.boot()
        self.assertIsNone(win.career.catalog)
        collections = [win.session.collection, win.ai.collection]
        before = [collection.observation_context() for collection in collections]
        win.go_career()
        guikit.pump()
        page = win.career.roadmap
        self.assertIs(win.pages.currentWidget(), page)
        self.assertEqual(win.area, "career_roadmap")
        page.select_role("qa")
        page.choose_goal()
        selected = json.loads(win.settings.value("career/role/" + win.user))
        self.assertEqual(selected["role_id"], page.selected_role_id)
        self.assertEqual(selected["catalog_version"], page.catalog.version)
        win.career.roadmap = None
        win.go_career()
        guikit.pump()
        self.assertEqual(win.career.roadmap.selected_role_id, selected["role_id"])
        self.assertEqual(win.career.roadmap.goal_button.text(), "저장한 관심 직무")
        after = [collection.observation_context() for collection in collections]
        for old, new in zip(before, after):
            self.assertEqual(old["epoch"], new["epoch"])
            self.assertEqual(old["goal"], new["goal"])

    def assert_career_menu(self, workspace, expanded, active):
        toggle = workspace.career_toggle
        self.assertEqual(toggle.property("expanded"), expanded)
        action = "커리어 메뉴 접기" if expanded else "커리어 메뉴 펼치기"
        self.assertEqual(toggle.toolTip(), action)
        self.assertEqual(toggle.accessibleDescription(), action)
        for key in ("career_roadmap", "career_magazine"):
            self.assertEqual(workspace.buttons[key].isHidden(), not expanded)
        selected = [button.key for button in (*workspace.buttons.values(), toggle) if button.isChecked()]
        self.assertEqual(selected, ["career" if active.startswith("career_") and not expanded else active])
        self.assertEqual(workspace.win.area, active)
        self.assertEqual(workspace.compact.currentData(),
                         next(action for key, _, action in workspace.subjects if key == active))

    def assert_career_icon(self, toggle, expanded):
        image = toggle.grab().toImage()
        ratio = image.devicePixelRatio()
        ink = "selection_ink" if toggle.isChecked() else "muted"
        # 중앙에 그린 실제 화소에서 두 아이콘의 크기와 방향·중심을 구함.
        for left, right, center, chevron in ((5, 45, 26, False),
                                              (toggle.width() - 42, toggle.width() - 5, toggle.width() - 24, True)):
            points = []
            for x in range(round(left * ratio), round(right * ratio)):
                for y in range(round(8 * ratio), image.height() - round(8 * ratio)):
                    color = image.pixelColor(x, y)
                    if color.alpha() >= 220 and guikit.near(color, ink):
                        points.append(((x + 0.5) / ratio, (y + 0.5) / ratio))
            self.assertTrue(points, (ink, left, right))
            xs, ys = zip(*points)
            width, height = max(xs) - min(xs), max(ys) - min(ys)
            self.assertAlmostEqual((min(xs) + max(xs)) / 2, center, delta=1.5)
            self.assertAlmostEqual((min(ys) + max(ys)) / 2, toggle.height() / 2, delta=1.5)
            if chevron:
                self.assertGreaterEqual(max(width, height), 17)
                self.assertGreaterEqual(min(width, height), 9)
                self.assertEqual(width > height, expanded)
            else:
                self.assertGreaterEqual(min(width, height), 17)

    def capture_navigation(self, win, name):
        if not os.environ.get("CAREER_EVIDENCE"):
            return
        from PyQt6.QtCore import QPoint
        out = Path(os.environ["CAREER_EVIDENCE"])
        out.mkdir(parents=True, exist_ok=True)
        win.repaint()
        guikit.pump()
        self.assertTrue(win.grab().save(str(out / (name + ".png"))))
        if guikit.APP.platformName() == "offscreen":
            return
        screen = win.screen()
        self.assertTrue(screen.availableGeometry().contains(win.frameGeometry()))
        if sys.platform == "win32":
            desktop = screen.grabWindow(0)
            ratio = desktop.devicePixelRatioF()
            origin = win.mapToGlobal(QPoint()) - screen.geometry().topLeft()
            native = desktop.copy(round(origin.x() * ratio), round(origin.y() * ratio),
                                  round(win.width() * ratio), round(win.height() * ratio))
        else:
            native = screen.grabWindow(int(win.winId()))
        self.assertTrue(native.save(str(out / (name + "-native.png"))))

    def test_career_navigation_hierarchy_fits_and_compact_keeps_both_entries(self):
        from PyQt6.QtCore import QPoint, Qt
        from PyQt6.QtGui import QFontMetricsF
        from PyQt6.QtTest import QTest

        self.addCleanup(theme.set_mode, theme.state["mode"])
        self.addCleanup(theme.set_text, theme.state["text"])
        win = self.boot()
        win.activateWindow()
        workspace = win.workspace
        toggle, picker = workspace.career_toggle, workspace.compact
        roadmap = workspace.buttons["career_roadmap"]
        magazine = workspace.buttons["career_magazine"]
        self.assert_career_menu(workspace, False, "hub")
        win.set_text("larger")
        bounds = win.screen().availableGeometry()
        large = (1600, 900)
        if guikit.APP.platformName() != "offscreen":
            margins = win.windowHandle().frameMargins()
            large = (min(1600, bounds.width() - margins.left() - margins.right() - 24),
                     min(900, bounds.height() - margins.top() - margins.bottom() - 24))
        win.move(bounds.topLeft() + QPoint(12, 12))
        for mode in ("light", "dark"):
            with self.subTest(theme=mode):
                win.set_theme(mode)
                win.resize(*large)
                win.go_career()
                guikit.pump()
                self.assertEqual((win.width(), win.height()), large)
                self.assertTrue(workspace.rail.isVisible())
                self.assert_career_menu(workspace, False, "career_roadmap")
                self.assert_career_icon(toggle, False)
                self.capture_navigation(win, f"career-large-collapsed-{mode}")
                toggle.setFocus()
                for _ in range(2):
                    QTest.keyClick(toggle, Qt.Key.Key_Right)
                    self.assert_career_menu(workspace, True, "career_roadmap")
                self.assert_career_icon(toggle, True)
                if mode == "light":
                    win.set_text("normal")
                    guikit.pump()
                    win.set_text("larger")
                    guikit.pump()
                metrics = QFontMetricsF(theme.font("label", True))
                for button in (toggle, *workspace.buttons.values()):
                    self.assertLessEqual(metrics.horizontalAdvance(button.text()), button.text_rect().width())
                    self.assertTrue(workspace.rail.rect().contains(button.geometry()))
                    if button.depth:
                        self.assertGreater(button.text_rect().left(), toggle.text_rect().left())
                self.capture_navigation(win, f"career-large-expanded-{mode}")
                QTest.keyClick(toggle, Qt.Key.Key_Tab)
                self.assertTrue(roadmap.hasFocus())
                QTest.keyClick(roadmap, Qt.Key.Key_Tab)
                self.assertTrue(magazine.hasFocus())
                QTest.keyClick(magazine, Qt.Key.Key_Return)
                self.assertIs(win.pages.currentWidget(), win.career.magazine)
                self.assert_career_menu(workspace, True, "career_magazine")
                toggle.setFocus()
                QTest.keyClick(toggle, Qt.Key.Key_Space)
                self.assert_career_menu(workspace, False, "career_magazine")
                QTest.keyClick(toggle, Qt.Key.Key_Left)
                self.assert_career_menu(workspace, False, "career_magazine")

                win.resize(1200, 480)
                guikit.pump()
                self.assertEqual((win.width(), win.height()), (1200, 480))
                self.assertFalse(workspace.rail.isVisible())
                self.assertTrue(picker.hasFocus())
                self.capture_navigation(win, f"career-wide-short-{mode}")
                win.resize(760, 480)
                guikit.pump()
                self.assertEqual((win.width(), win.height()), (760, 480))
                self.assertTrue(picker.isVisible())
                self.assertEqual(picker.currentText(), "커리어 · 매거진")
                self.capture_navigation(win, f"career-small-{mode}")
                QTest.mouseClick(picker, guikit.LEFT, pos=QPoint(picker.width() - 24, picker.height() // 2))
                guikit.wait_until(picker.view().isVisible)
                QTest.keyClick(picker.view(), Qt.Key.Key_Escape)
                guikit.wait_until(lambda: not picker.view().isVisible())
                if guikit.APP.platformName() == "offscreen":
                    # 창 관리자가 없는 플랫폼에서는 팝업을 닫은 뒤 활성 창을 복원함.
                    win.activateWindow()
                    guikit.pump()
                self.assertTrue(picker.hasFocus())
                QTest.keyClick(picker, Qt.Key.Key_Up)
                self.assertEqual(picker.currentText(), "커리어 · 개발자 로드맵")
                self.assertIs(win.pages.currentWidget(), win.career.roadmap)
                win.resize(*large)
                guikit.pump()
                self.assertTrue(toggle.hasFocus())
                self.assert_career_menu(workspace, False, "career_roadmap")
                guikit.click(toggle)
                win.resize(760, 480)
                guikit.pump()
                win.resize(*large)
                guikit.pump()
                self.assertTrue(roadmap.hasFocus())
                self.assert_career_menu(workspace, True, "career_roadmap")
                toggle.setFocus()
                QTest.keyClick(toggle, Qt.Key.Key_Left)
                self.assert_career_menu(workspace, False, "career_roadmap")
        self.capture_widget = win

    def test_related_video_opens_without_playing_and_page_exit_requests_stop(self):
        win = self.boot()
        win.go_magazine()
        page = win.career.magazine
        play, stop = mock.Mock(), mock.Mock()
        page.on_video, page.on_stop = play, stop
        page.search.setText("검색 결과 없음")
        win.career.show_magazine("H89Az-iZZrc")
        guikit.pump()
        self.assertEqual(page.selected_video_id, "H89Az-iZZrc")
        play.assert_not_called()
        self.assertIsNone(page.info_dialog)
        self.assertEqual("검색 결과 없음", page.search.text())
        cover = page.rows[page.selected_video_id].cover
        self.assertTrue(cover.hasFocus())
        self.assertFalse(cover.visibleRegion().isEmpty())
        from PyQt6.QtCore import Qt
        from PyQt6.QtTest import QTest
        QTest.keyClick(cover, Qt.Key.Key_Return)
        play.assert_called_once()
        win.go_career()
        guikit.pump()
        stop.assert_called_once()
        self.assertIsNone(page._requested_id)

    def test_browsing_filtering_and_return_never_reopen_clicked_video(self):
        from gui.video_viewer import EngineUnavailable
        win = self.boot()
        win.open_url = mock.Mock(return_value=True)
        with mock.patch("gui.video_viewer.create_engine", side_effect=EngineUnavailable("재생기 미설치")) as factory, \
                mock.patch("tools.video_setup.install") as install:
            win.go_magazine()
            page = win.career.magazine
            video = next(v for v in page.catalog.videos if v.embeddable is not False)
            page.search.setText(video.title)
            page._change_tab(1)
            page._change_tab(0)
            guikit.pump()
            win.open_url.assert_not_called()
            factory.assert_not_called()
            guikit.click(page.rows[video.video_id].cover)
            win.open_url.assert_called_once_with("https://www.youtube.com/watch?v=" + video.video_id)
            factory.assert_called_once()
            self.assertIsNone(win.career.video)
            self.assertIsNone(page._requested_id)
            win.go_career()
            win.go_magazine()
            page.search.clear()
            guikit.pump()
            self.assertEqual(1, win.open_url.call_count)
            self.assertEqual(1, factory.call_count)
            install.assert_not_called()

    def test_ended_video_close_releases_dialog_independently_of_magazine_request(self):
        from PyQt6.QtWidgets import QWidget
        win = self.boot()
        win.go_magazine()
        engines = []

        class Engine:
            def __init__(self, parent, event, open_url):
                self.widget = QWidget(parent)
                self.event, self.closed = event, False
                engines.append(self)

            def start(self, video_id):
                self.event("ready")

            def close(self):
                self.closed = True
                self.widget.deleteLater()

        with mock.patch("gui.video_viewer.create_engine", Engine):
            win.career.magazine.play_video()
            guikit.pump()
            dialog = win.career.video
            engines[0].event("state", 0)
            self.assertIsNone(win.career.magazine._requested_id)
            dialog.close()
            guikit.pump()
            self.assertIsNone(win.career.video)
            self.assertTrue(engines[0].closed)

    def test_late_video_preparation_result_does_not_call_deleted_dialog(self):
        from gui.video_viewer import EngineUnavailable
        release = threading.Event()
        win = self.boot()
        win.go_magazine()

        def install(cancel):
            release.wait(3)
            return {"ok": True}

        win.open_url = mock.Mock(return_value=False)
        with mock.patch("gui.video_viewer.create_engine", side_effect=EngineUnavailable("재생기 미설치")), \
                mock.patch("tools.video_setup.install", install):
            win.career.magazine.play_video()
            guikit.pump()
            dialog = win.career.video
            dialog.prepare()
            self.assertIsNotNone(win.career.setup_job)
            win.career.stop_video()
            guikit.pump()
            release.set()
            guikit.wait_until(lambda: win.career.setup_job is None)
            self.assertIsNone(win.career.video)

    def test_paper_callbacks_keep_study_records_and_footer_in_small_parent(self):
        from PyQt6.QtCore import QPoint
        win = self.boot()
        win.go_magazine()
        win.resize(760, 480)
        before = win.session.collection.observation_context()
        for mode in ("light", "dark"):
            win.set_theme(mode)
            win.set_text("larger")
            for paper in win.career.catalog.papers:
                win.career.explain_paper(paper)
                dialog = win.career.paper
                guikit.pump()
                self.assertLessEqual(dialog.width(), win.width())
                self.assertLessEqual(dialog.height(), win.height())
                for stage in range(4):
                    dialog.set_stage(stage)
                    guikit.wait_until(lambda: not dialog._restoring)
                    for button in (dialog.previous, dialog.next, dialog.close_button):
                        rect = button.geometry().translated(button.parentWidget().mapTo(dialog, QPoint()))
                        self.assertTrue(dialog.rect().contains(rect), (paper.paper_id, stage, button.text(), rect))
                        self.assertGreaterEqual(button.width(), button.fontMetrics().horizontalAdvance(button.text()))
                    evidence = os.environ.get("CAREER_EVIDENCE")
                    if evidence:
                        out = Path(evidence)
                        out.mkdir(parents=True, exist_ok=True)
                        prefix = f"paper-{paper.paper_id}-{mode}-{stage}"
                        self.assertTrue(dialog.grab().save(str(out / (prefix + ".png"))))
                        if sys.platform == "win32":
                            native = dialog.screen().grabWindow(int(dialog.winId()))
                            self.assertFalse(native.isNull())
                            self.assertTrue(native.save(str(out / (prefix + "-native.png"))))
                dialog.close()
                guikit.pump()
                self.assertIsNone(win.career.paper)
        after = win.session.collection.observation_context()
        self.assertEqual(before["goal"], after["goal"])
        self.assertEqual(before["epoch"], after["epoch"])
        self.capture_widget = win


if __name__ == "__main__":
    unittest.main()
