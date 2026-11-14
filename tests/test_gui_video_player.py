"""실제 엔진·설치·학습 기록 없이 재생 창의 상태와 배치를 확인함."""
import os
import sys
import subprocess
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest import mock

from tests import guikit
from PyQt6.QtCore import QObject, QPoint, Qt, QUrl, pyqtSignal
from PyQt6.QtWidgets import QWidget

from gui import kit, theme
from gui.video_viewer import EngineUnavailable, PLAYER_TIMEOUT_MS, VideoDialog, VideoSurface, create_engine

VIDEO = SimpleNamespace(video_id="H89Az-iZZrc", title="로봇 개발자의 실제 업무와 학습 순서를 살펴봅니다", author="공개 영상 제작자", embeddable=True)


class FakeEngine:
    def __init__(self, parent, on_event, open_url):
        self.widget = QWidget(parent)
        self.widget.setMinimumSize(200, 200)
        self.on_event, self.open_url = on_event, open_url
        self.start = mock.Mock()
        self.close = mock.Mock(side_effect=self.widget.hide)
        self.exit_fullscreen = mock.Mock()


class VideoDialogTest(unittest.TestCase):
    def setUp(self):
        self.mode, self.text = theme.state["mode"], theme.state["text"]
        self.host = QWidget()
        self.host.resize(1024, 700)
        self.host.show()
        self.dialogs, self.engines = [], []
        self.external, self.prepare = mock.Mock(), mock.Mock()

    def tearDown(self):
        for dialog in self.dialogs:
            dialog.close()
            dialog.deleteLater()
        self.host.close()
        theme.set_text(self.text)
        theme.set_mode(self.mode)
        guikit.pump()

    def engine(self, *args):
        engine = FakeEngine(*args)
        self.engines.append(engine)
        return engine

    def dialog(self, factory=None, video=VIDEO, show=True):
        dialog = VideoDialog(self.host, video, self.external, self.prepare, factory or self.engine)
        self.dialogs.append(dialog)
        if show:
            dialog.open()
            guikit.pump()
        return dialog

    def unavailable(self):
        # 브라우저 실행도 실패했을 때만 선택형 설치를 표시함.
        self.external.return_value = False
        with mock.patch("gui.video_viewer.find_spec", return_value=None):
            return self.dialog(create_engine)

    def test_import_does_not_load_webengine_or_start_a_process(self):
        code = ("import sys; from unittest.mock import patch; "
                "p=patch('subprocess.Popen',side_effect=AssertionError('process')); p.start(); "
                "import gui.video_viewer; import tools.video_setup; "
                "assert not any('QtWebEngine' in n for n in sys.modules)")
        result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)

    def test_constructor_never_creates_engine_or_prepares(self):
        factory = mock.Mock()
        dialog = self.dialog(factory, show=False)
        self.assertEqual("idle", dialog.state)
        factory.assert_not_called()
        self.prepare.assert_not_called()

    def test_first_document_native_parent_recreation_does_not_stop_playback(self):
        def factory(parent, on_event, open_url):
            engine = self.engine(parent, on_event, open_url)
            engine.start.side_effect = lambda _: parent.window().hide()
            return engine

        dialog = self.dialog(factory)
        self.assertTrue(dialog.isVisible())
        self.assertIs(dialog.engine, self.engines[-1])
        self.engines[-1].close.assert_not_called()
        self.engines[-1].on_event("state", 1)
        self.assertEqual(dialog.state, "playing")
        dialog.hide()
        self.assertIsNone(dialog.engine)
        self.engines[-1].close.assert_called_once()

    def test_close_during_first_document_never_reopens_the_window(self):
        def factory(parent, on_event, open_url):
            engine = self.engine(parent, on_event, open_url)
            engine.start.side_effect = lambda _: parent.window().close()
            return engine

        dialog = self.dialog(factory)
        self.assertTrue(dialog.closed)
        self.assertFalse(dialog.isVisible())
        self.assertIsNone(dialog.engine)

    def test_requested_ready_blocked_and_buffering_never_claim_playing(self):
        dialog = self.dialog()
        engine = self.engines[-1]
        engine.start.assert_called_once_with(VIDEO.video_id)
        self.assertEqual("requesting", dialog.state)
        for kind, code, expected in (("ready", None, "ready"), ("blocked", None, "ready"),
                                     ("state", 3, "buffering"), ("state", -1, "ready"),
                                     ("state", 1, "playing"), ("state", 2, "paused")):
            engine.on_event(kind, code)
            self.assertEqual(expected, dialog.state)
        self.assertIs(dialog.engine, engine)
        self.external.assert_not_called()
        self.prepare.assert_not_called()

    def test_errors_release_engine_and_ignore_late_playing(self):
        for code in (100, 101, 150, 153, 5, 0):
            dialog = self.dialog()
            engine = self.engines[-1]
            engine.on_event("state", 1)
            engine.on_event("error", code)
            self.assertEqual("error", dialog.state)
            self.assertIsNone(dialog.engine)
            engine.close.assert_called_once()
            engine.on_event("state", 1)
            self.assertEqual("error", dialog.state)
            self.assertTrue(dialog.retry_button.isVisible())
            self.external.assert_not_called()
            dialog.close()

    def test_first_embed_denial_opens_selected_watch_url_once_then_ignores_old_events(self):
        for code in (101, 150):
            video = SimpleNamespace(**dict(vars(VIDEO), embeddable=None, url="https://example.test"))
            dialog = self.dialog(video=video)
            engine = dialog.engine
            engine.on_event("ready")
            engine.on_event("state", 3)
            engine.on_event("error", code)
            self.assertTrue(dialog.closed)
            self.assertFalse(dialog.isVisible())
            engine.close.assert_called_once()
            engine.on_event("error", code)
            engine.open_url("https://www.youtube.com/watch?v=" + video.video_id)
            self.external.assert_called_once_with("https://www.youtube.com/watch?v=" + video.video_id)
            self.external.reset_mock()
            self.prepare.assert_not_called()

    def test_embed_denial_after_autoplay_block_or_retry_stays_in_the_dialog(self):
        dialog = self.dialog()
        dialog.engine.on_event("blocked")
        dialog.engine.on_event("error", 150)
        self.assertEqual("error", dialog.state)
        dialog.play()
        dialog.engine.on_event("error", 101)
        self.assertEqual("error", dialog.state)
        self.external.assert_not_called()

    def test_denial_after_initial_load_window_does_not_open_a_browser(self):
        with mock.patch("gui.video_viewer.monotonic", return_value=10) as clock:
            dialog = self.dialog()
            engine = dialog.engine
            engine.on_event("ready")
            clock.return_value += PLAYER_TIMEOUT_MS / 1000
            engine.on_event("error", 150)
            self.assertEqual("error", dialog.state)
            self.external.assert_not_called()

    def test_stop_close_hide_and_retry_invalidate_old_callbacks(self):
        dialog = self.dialog()
        first = self.engines[-1]
        first.on_event("state", 1)
        guikit.click(dialog.stop_button)
        self.assertEqual("stopped", dialog.state)
        first.close.assert_called_once()
        guikit.click(dialog.retry_button)
        second = self.engines[-1]
        first.on_event("state", 1)
        self.assertEqual("requesting", dialog.state)
        second.on_event("state", 1)
        dialog.hide()
        self.assertEqual("stopped", dialog.state)
        second.close.assert_called_once()
        dialog.close()
        second.on_event("state", 1)
        self.assertEqual("closed", dialog.state)

    def test_escape_and_parent_close_release_resources(self):
        from PyQt6.QtTest import QTest
        dialog = self.dialog()
        engine = self.engines[-1]
        QTest.keyClick(dialog, Qt.Key.Key_Escape)
        guikit.pump()
        self.assertTrue(dialog.closed)
        engine.close.assert_called_once()
        other = self.dialog()
        engine = self.engines[-1]
        self.host.hide()
        other.hide()
        engine.close.assert_called_once()

    def test_known_unavailability_opens_only_browser_in_click_call(self):
        for error in (EngineUnavailable("missing"), EngineUnavailable("restart", "restart"),
                      ImportError("library"), RuntimeError("initialization"), None):
            with self.subTest(error=error):
                video = SimpleNamespace(**dict(vars(VIDEO), embeddable=bool(error), url="https://example.test/"))
                factory = mock.Mock(side_effect=error)
                dialog = self.dialog(factory, video, show=False)
                with mock.patch.object(dialog, "showEvent", wraps=dialog.showEvent) as shown:
                    dialog.open()
                    self.external.assert_called_once_with("https://www.youtube.com/watch?v=" + VIDEO.video_id)
                    dialog.open()
                    guikit.pump()
                    shown.assert_not_called()
                self.assertTrue(dialog.closed)
                self.assertIsNone(dialog.engine)
                self.assertEqual(int(error is not None), factory.call_count)
                self.prepare.assert_not_called()
                self.external.reset_mock()

    def test_start_failure_after_cancel_and_old_link_after_retry_do_not_navigate(self):
        def factory(parent, on_event, open_url):
            engine = self.engine(parent, on_event, open_url)
            def cancelled(_):
                parent.window().close()
                raise RuntimeError("closed")
            engine.start.side_effect = cancelled
            return engine

        self.assertTrue(self.dialog(factory).closed)
        dialog = self.dialog()
        first = self.engines[-1]
        dialog.stop()
        dialog.play()
        first.open_url("https://www.youtube.com/watch?v=" + VIDEO.video_id)
        first.on_event("error", 101)
        self.assertIs(dialog.engine, self.engines[-1])
        self.external.assert_not_called()

    def test_preparation_is_explicit_idempotent_and_late_completion_is_ignored(self):
        cancel = mock.Mock()
        self.prepare.return_value = cancel
        dialog = self.unavailable()
        self.assertTrue(dialog.prepare_button.isVisible())
        self.prepare.assert_not_called()
        guikit.click(dialog.prepare_button)
        self.assertEqual("preparing", dialog.state)
        self.prepare.assert_called_once()
        done = self.prepare.call_args.args[0]
        dialog.prepare()
        self.prepare.assert_called_once()
        dialog.close()
        cancel.assert_called_once()
        self.assertFalse(done({"ok": True, "restart": True}))
        self.assertEqual("closed", dialog.state)

    def test_failed_cancelled_and_successful_preparation_have_distinct_states(self):
        for result, state in (({"ok": False, "status": "error"}, "unavailable"),
                              ({"ok": False, "status": "cancelled"}, "unavailable"),
                              ({"ok": True, "restart": True}, "restart")):
            self.prepare.side_effect = lambda done, result=result: done(result)
            dialog = self.unavailable()
            guikit.click(dialog.prepare_button)
            self.assertEqual(state, dialog.state)
            self.assertIsNone(dialog.cancel_prepare)
            dialog.close()

    def test_stop_invalidates_even_a_synchronous_completion_from_cancel(self):
        accepted = []
        def prepare(done):
            return lambda: accepted.append(done({"ok": True, "restart": True}))
        self.prepare.side_effect = prepare
        dialog = self.unavailable()
        guikit.click(dialog.prepare_button)
        dialog.stop()
        self.assertEqual([False], accepted)
        self.assertEqual("stopped", dialog.state)

    def test_close_from_a_state_listener_does_not_start_engine_or_installer(self):
        factory = mock.Mock()
        dialog = self.dialog(factory, show=False)
        dialog.state_changed.connect(lambda state: dialog.close() if state == "requesting" else None)
        dialog.open()
        guikit.pump()
        factory.assert_not_called()
        pending = self.unavailable()
        pending.state_changed.connect(lambda state: pending.close() if state == "preparing" else None)
        guikit.click(pending.prepare_button)
        self.prepare.assert_not_called()

    def test_unsupported_initialization_and_embed_denial_never_install(self):
        self.external.return_value = False
        dialog = self.dialog(mock.Mock(side_effect=EngineUnavailable("다시 시작해 주세요.", "restart")))
        self.assertEqual("restart", dialog.state)
        self.assertTrue(dialog.prepare_button.isHidden())
        factory = mock.Mock()
        denied = self.dialog(factory, SimpleNamespace(**dict(vars(VIDEO), embeddable=False)))
        self.assertEqual("error", denied.state)
        factory.assert_not_called()
        self.prepare.assert_not_called()

    def test_engine_check_does_not_import_when_missing_or_not_initialized(self):
        with mock.patch("gui.video_viewer.find_spec", return_value=None), self.assertRaises(EngineUnavailable):
            create_engine(self.host, mock.Mock(), mock.Mock())
        with mock.patch("gui.video_viewer.find_spec", return_value=object()), \
                mock.patch("gui.video_viewer.QCoreApplication.testAttribute", return_value=False):
            with self.assertRaises(EngineUnavailable) as error:
                create_engine(self.host, mock.Mock(), mock.Mock())
            self.assertEqual("restart", error.exception.state)

    def test_present_module_with_failed_library_load_uses_error_fallback(self):
        original = __import__
        def failed_import(name, *args, **kwargs):
            if name == "PyQt6.QtWebEngineCore":
                raise ImportError("mock missing shared library")
            return original(name, *args, **kwargs)
        with mock.patch("gui.video_viewer.find_spec", return_value=object()), \
                mock.patch("gui.video_viewer.QCoreApplication.testAttribute", return_value=True), \
                mock.patch("builtins.__import__", side_effect=failed_import):
            with self.assertRaises(EngineUnavailable) as error:
                create_engine(self.host, mock.Mock(), mock.Mock())
        self.assertEqual("error", error.exception.state)
        self.assertNotIn("다시 준비", str(error.exception))

    def test_official_open_stops_playback_and_does_not_trust_catalog_url(self):
        video = SimpleNamespace(**dict(vars(VIDEO), url="https://private.example/secret"))
        dialog = self.dialog(video=video)
        engine = self.engines[-1]
        guikit.click(dialog.source_button)
        self.external.assert_called_once_with("https://www.youtube.com/watch?v=" + VIDEO.video_id)
        engine.close.assert_called_once()
        self.assertTrue(dialog.closed)
        self.assertFalse(dialog.isVisible())
        self.external.reset_mock()
        dialog._external("https://accounts.google.com/")
        self.external.assert_not_called()

    def assert_footer(self, dialog):
        previous, stable = None, 0
        def settled():
            nonlocal previous, stable
            dialog.layout().activate()
            current = (dialog.size(), dialog.shell.scroll.verticalScrollBar().maximum(),
                       tuple((widget.geometry(), widget.isVisible(), widget.font().toString())
                             for widget in dialog.findChildren(QWidget)))
            stable = stable + 1 if current == previous else 0
            previous = current
            return stable >= 3
        guikit.wait_until(settled, timeout=3)
        for button in (dialog.source_button, dialog.close_button, dialog.prepare_button, dialog.retry_button, dialog.stop_button):
            if not button.isVisible():
                continue
            rect = button.geometry().translated(button.parentWidget().mapTo(dialog, QPoint()))
            self.assertTrue(dialog.rect().contains(rect), (button.text(), rect, dialog.size()))
            self.assertGreaterEqual(button.width(), button.sizeHint().width(), button.text())
            self.assertGreater(rect.top(), dialog.shell.scroll.geometry().bottom())
            self.assertGreater(button.grab().toImage().width(), 0)

    def test_small_large_windows_maximum_text_and_two_themes_keep_footer_visible(self):
        theme.set_text("larger")
        evidence = os.environ.get("VIDEO_EVIDENCE")
        sizes = ((760, 480), (1024, 700), (1280, 800))
        if os.name == "nt":
            room = self.host.screen().availableGeometry()
            sizes = tuple((min(w, room.width() - 32), min(h, room.height() - 64)) for w, h in sizes)
            self.host.move(room.topLeft() + QPoint(16, 32))
            if evidence:
                import json
                Path(evidence).mkdir(parents=True, exist_ok=True)
                (Path(evidence) / "video-window-sizes.json").write_text(json.dumps({"requested": [[760, 480], [1024, 700], [1280, 800]], "tested": sizes,
                    "available": [room.width(), room.height()], "scope": "Native large cases fit the runner. Full sizes remain offscreen;760x480 unchanged."}, indent=2))
        for mode in ("light", "dark"):
            theme.set_mode(mode)
            for width, height in sizes:
                self.host.resize(width, height)
                dialog = self.unavailable()
                dialog.resize(width - 40, height - 40)
                kit.refont(dialog)
                guikit.pump()
                dialog._place()
                guikit.pump()
                self.assertEqual((width - 40, height - 40), (dialog.width(), dialog.height()))
                self.assert_footer(dialog)
                if evidence:
                    Path(evidence).mkdir(parents=True, exist_ok=True)
                    dialog.grab().save(str(Path(evidence) / f"unavailable-{mode}-{width}x{height}.png"))
                    if os.name == "nt":
                        dialog.screen().grabWindow(int(dialog.winId())).save(str(Path(evidence) / f"unavailable-{mode}-{width}x{height}-native.png"))
                if mode == "dark" and (width, height) == sizes[-1]:
                    self.capture_widget = dialog
                else:
                    dialog.close()

    def test_small_viewport_does_not_construct_an_undersized_player(self):
        dialog = self.dialog(show=False)
        dialog.resize(200, 400)
        with mock.patch.object(dialog.shell, "fit"):
            dialog.open()
            guikit.pump()
        self.assertEqual([], self.engines)
        self.external.assert_called_once_with("https://www.youtube.com/watch?v=" + VIDEO.video_id)
        self.assertTrue(dialog.closed)

    def test_playing_and_preparing_footer_survives_font_change_and_fullscreen_exit(self):
        theme.set_text("larger")
        dialog = self.dialog()
        engine = self.engines[-1]
        dialog.resize(720, 440)
        engine.on_event("state", 1)
        guikit.pump()
        self.assert_footer(dialog)
        engine.on_event("fullscreen", True)
        guikit.pump()
        self.assertTrue(dialog._fullscreen)
        engine.on_event("fullscreen", False)
        guikit.pump()
        self.assertIs(dialog.engine, engine)
        self.assertFalse(dialog._fullscreen)
        engine.close.assert_not_called()
        self.assert_footer(dialog)
        dialog.close()
        pending = self.unavailable()
        guikit.click(pending.prepare_button)
        pending.resize(720, 440)
        guikit.pump()
        self.assert_footer(pending)

    def test_live_text_changes_keep_rendered_glyphs_and_controls_consistent(self):
        dialog = self.unavailable()
        dialog.resize(720, 440)
        for step in ("normal", "larger", "normal", "larger"):
            theme.set_text(step)
            kit.refont(dialog)
            self.assert_footer(dialog)
            peer = kit.para(dialog.status.text(), "body")
            peer.setParent(dialog.shell.body)
            peer.setGeometry(dialog.status.geometry())
            peer.show()
            guikit.pump()
            self.assertEqual(dialog.status.font(), peer.font())
            self.assertEqual(dialog.status.grab().toImage(), peer.grab().toImage())
            peer.hide()
            peer.deleteLater()

    def test_video_surface_preserves_its_available_width_and_aspect(self):
        dialog = self.dialog()
        for width in (720, 1000, 1200):
            dialog.resize(width, 650)
            self.assert_footer(dialog)
            self.assertGreaterEqual(dialog.engine.widget.width(), 200)
            self.assertGreaterEqual(dialog.engine.widget.height(), 200)
            self.assertLessEqual(abs(dialog.surface.height() - max(200, round(dialog.surface.width() * 9 / 16))), 1)

    def test_autoplay_requires_more_than_half_the_surface_in_the_viewport(self):
        viewport = QWidget(self.host)
        viewport.setGeometry(5, 5, 320, 200)
        surface = VideoSurface(viewport)
        surface.setFixedSize(320, 200)
        viewport.show()
        surface.show()
        for offset, expected in ((0, True), (99, True), (100, False), (101, False)):
            surface.move(0, offset)
            self.assertEqual(expected, surface.can_autoplay())
        surface.move(0, 0)
        viewport.hide()
        self.assertFalse(surface.can_autoplay())

    def test_hiding_fullscreen_releases_without_showing_the_dialog_again(self):
        dialog = self.dialog()
        engine = self.engines[-1]
        engine.on_event("fullscreen", True)
        guikit.pump()
        dialog.hide()
        guikit.pump()
        engine.close.assert_called_once()
        self.assertFalse(dialog.isVisible())
        self.assertFalse(dialog._fullscreen)
        self.assertEqual("stopped", dialog.state)


class EnginePolicyTest(unittest.TestCase):
    """실제 WebEngine을 가져오지 않고 Qt 어댑터의 호출 계약을 확인함."""

    def setUp(self):
        class Profile(QObject):
            downloadRequested = pyqtSignal(object)
            HttpCacheType = SimpleNamespace(MemoryHttpCache=1)
            PersistentCookiesPolicy = SimpleNamespace(NoPersistentCookies=2)
            PersistentPermissionsPolicy = SimpleNamespace(AskEveryTime=3)

            def __init__(self):
                super().__init__()
                for name in ("setHttpCacheType", "setHttpCacheMaximumSize", "setPersistentCookiesPolicy",
                             "setPersistentPermissionsPolicy", "setUrlRequestInterceptor"):
                    setattr(self, name, mock.Mock())

        class Page(QObject):
            featurePermissionRequested = pyqtSignal(object, object)
            permissionRequested = pyqtSignal(object)
            fileSystemAccessRequested = pyqtSignal(object)
            newWindowRequested = pyqtSignal(object)
            fullScreenRequested = pyqtSignal(object)
            loadFinished = pyqtSignal(bool)
            renderProcessTerminated = pyqtSignal(object, object)
            NavigationType = SimpleNamespace(NavigationTypeLinkClicked=0, NavigationTypeOther=5)
            PermissionPolicy = SimpleNamespace(PermissionDeniedByUser=1)
            LifecycleState = SimpleNamespace(Discarded=2)

            def __init__(self, profile, parent):
                super().__init__(parent)
                self.options = SimpleNamespace(setAttribute=mock.Mock())
                for name in ("setFeaturePermission", "setHtml", "runJavaScript", "setAudioMuted",
                             "setVisible", "setLifecycleState"):
                    setattr(self, name, mock.Mock())

            def settings(self):
                return self.options

        class View(QWidget):
            def __init__(self, parent):
                super().__init__(parent)
                self.stop = mock.Mock()

            def setPage(self, page):
                self.page_object = page

        names = ("FullScreenSupportEnabled", "PlaybackRequiresUserGesture", "JavascriptCanOpenWindows",
                 "JavascriptCanAccessClipboard", "LocalContentCanAccessFileUrls", "LocalContentCanAccessRemoteUrls")
        core = SimpleNamespace(QWebEnginePage=Page, QWebEngineProfile=Profile, QWebEngineUrlRequestInterceptor=QObject,
                               QWebEngineSettings=SimpleNamespace(WebAttribute=SimpleNamespace(**{name: name for name in names})))
        patches = (mock.patch.dict(sys.modules, {"PyQt6.QtWebEngineCore": core,
                                                "PyQt6.QtWebEngineWidgets": SimpleNamespace(QWebEngineView=View)}),
                   mock.patch("gui.video_viewer.find_spec", return_value=object()),
                   mock.patch("gui.video_viewer.QCoreApplication.testAttribute", return_value=True))
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        self.parent = VideoSurface()
        self.event, self.external = mock.Mock(), mock.Mock()
        self.engine = create_engine(self.parent, self.event, self.external)
        self.engine.start(VIDEO.video_id)

    def tearDown(self):
        self.engine.close()
        self.parent.close()
        guikit.pump()

    def test_anonymous_profile_memory_cache_and_permissions(self):
        engine = self.engine
        self.assertIsNone(engine.profile.parent())
        engine.profile.setHttpCacheType.assert_called_once_with(1)
        engine.profile.setHttpCacheMaximumSize.assert_called_once_with(16 * 1024 * 1024)
        engine.profile.setPersistentCookiesPolicy.assert_called_once_with(2)
        engine.page.options.setAttribute.assert_any_call("PlaybackRequiresUserGesture", False)
        engine.page.options.setAttribute.assert_any_call("JavascriptCanOpenWindows", False)
        request = mock.Mock()
        engine.page.permissionRequested.emit(request)
        request.deny.assert_called_once()
        engine.page.featurePermissionRequested.emit(QUrl("https://www.youtube-nocookie.com"), "camera")
        self.assertEqual(1, engine.page.setFeaturePermission.call_args.args[-1])
        engine.profile.downloadRequested.emit(request)
        request.cancel.assert_called_once()
        engine.page.fileSystemAccessRequested.emit(request)
        request.reject.assert_called_once()

    def test_embed_request_header_and_selected_embed_navigation(self):
        from career.player_html import APP_ORIGIN, embed_url
        engine = self.engine
        request = mock.Mock()
        request.requestUrl.return_value = QUrl(embed_url(VIDEO.video_id))
        engine.interceptor.interceptRequest(request)
        request.setHttpHeader.assert_called_once_with(b"Referer", APP_ORIGIN.encode("ascii"))
        other = mock.Mock()
        other.requestUrl.return_value = QUrl("https://googleads.g.doubleclick.net/example")
        engine.interceptor.interceptRequest(other)
        other.setHttpHeader.assert_not_called()
        page = engine.page
        self.assertTrue(page.acceptNavigationRequest(QUrl(APP_ORIGIN + "/"), 5, True))
        self.assertFalse(page.acceptNavigationRequest(QUrl(APP_ORIGIN + "/"), 5, True))
        self.assertTrue(page.acceptNavigationRequest(QUrl(embed_url(VIDEO.video_id)), 5, False))
        self.assertFalse(page.acceptNavigationRequest(QUrl(embed_url("abcdefghijk")), 5, False))
        self.assertFalse(page.acceptNavigationRequest(QUrl("https://accounts.google.com"), 5, False))
        self.assertFalse(page.acceptNavigationRequest(QUrl("https://www.youtube.com/watch?v=" + VIDEO.video_id), 5, True))
        self.external.assert_not_called()
        self.assertFalse(page.acceptNavigationRequest(QUrl("https://www.youtube.com/watch?v=" + VIDEO.video_id), 0, True))
        self.external.assert_called_once()

    def test_embed_denial_keeps_prior_block_or_play_between_polls(self):
        self.engine.received({"kind": "error", "code": 101, "initial": False})
        self.event.assert_called_once_with("late_error", 101)

    def test_only_user_initiated_official_popups_are_forwarded(self):
        request = mock.Mock()
        request.requestedUrl.return_value = QUrl("https://www.youtube.com/watch?v=" + VIDEO.video_id)
        request.isUserInitiated.return_value = False
        self.engine.new_window(request)
        self.external.assert_not_called()
        request.isUserInitiated.return_value = True
        self.engine.new_window(request)
        self.external.assert_called_once()
        self.external.reset_mock()
        request.requestedUrl.return_value = QUrl("https://accounts.google.com/")
        self.engine.new_window(request)
        self.external.assert_not_called()

    def test_close_mutes_discards_and_ignores_late_javascript_results(self):
        engine = self.engine
        engine.poll()
        self.assertTrue(engine.pending)
        engine.close()
        engine.page.setAudioMuted.assert_called_once_with(True)
        engine.widget.stop.assert_called_once()
        engine.page.setLifecycleState.assert_called_once_with(2)
        engine.received({"kind": "state", "code": 1})
        self.event.assert_not_called()
        self.assertFalse(engine.poll_timer.isActive())
        self.assertFalse(engine.deadline.isActive())

    def test_blocked_load_and_timeout_report_errors_and_ready_is_not_playing(self):
        engine = self.engine
        engine.received({"kind": "ready"})
        self.event.assert_called_once_with("ready", None)
        self.assertFalse(engine.deadline.isActive())
        engine.loaded(False)
        self.event.assert_called_with("error", 0)
        engine.deadline.timeout.emit()
        self.event.assert_called_with("error", 0)


if __name__ == "__main__":
    unittest.main()
