"""사용자가 고른 공개 영상을 별도 창에서 재생하며 종료 뒤의 신호를 무시함."""
from __future__ import annotations

from importlib.util import find_spec
from time import monotonic

from PyQt6.QtCore import QCoreApplication, QEvent, QObject, QPoint, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import QDialog, QSizePolicy, QWidget

from career.player_html import (APP_ORIGIN, EMBED_HOST, checked_video_id, error_message,
                                external_video_link, is_embed_url, is_playback_frame, player_html, watch_url)
from gui import kit
from gui.dialog_layout import DialogLayout


PLAYER_TIMEOUT_MS = 25_000


class EngineUnavailable(RuntimeError):
    def __init__(self, message, state="unavailable"):
        super().__init__(message)
        self.state = state


class VideoSurface(QWidget):
    """가용 폭에 16:9를 적용하며 최소 재생 높이 200px를 보존함."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.fullscreen = False
        self.box = kit.box(self)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return max(200, round(width * 9 / 16))

    def sizeHint(self):
        return QSize(640, 360)

    def minimumSizeHint(self):
        return QSize(0, 200)

    def can_autoplay(self):
        if not self.isVisible() or self.window().isMinimized():
            return False
        # WebEngine의 불투명한 자식이 visibleRegion을 덮으므로 스크롤 뷰포트 등 부모들의 잘림을 직접 계산함.
        visible = self.screen().geometry()
        widget = self
        while widget is not None:
            visible = visible.intersected(widget.rect().translated(widget.mapToGlobal(QPoint())))
            if widget.isWindow():
                break
            widget = widget.parentWidget()
        return 2 * visible.width() * visible.height() > self.width() * self.height()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.setMinimumHeight(200 if self.fullscreen else self.heightForWidth(self.width()))


def create_engine(parent, on_event, open_url):
    """첫 재생 때만 모듈을 가져옴. 앱 생성 전의 공유 컨텍스트 설정은 진입점에서 맡음."""
    try:
        available = find_spec("PyQt6.QtWebEngineWidgets") is not None
    except (ImportError, ValueError):
        available = False
    if not available:
        raise EngineUnavailable("앱 내 재생기를 설치하면 이 창에서 볼 수 있습니다.")
    if not QCoreApplication.testAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts):
        raise EngineUnavailable("앱 내 재생기를 사용하려면 프로그램을 다시 시작해 주세요.", "restart")
    try:
        from PyQt6.QtWebEngineCore import (QWebEnginePage, QWebEngineProfile, QWebEngineSettings,
                                           QWebEngineUrlRequestInterceptor)
        from PyQt6.QtWebEngineWidgets import QWebEngineView
    except (ImportError, OSError, RuntimeError) as error:
        raise EngineUnavailable("앱 내 재생기를 불러오지 못했습니다.", "error") from error

    class Referrer(QWebEngineUrlRequestInterceptor):
        def interceptRequest(self, info):
            # 로컬 문서의 합성 원점에 기대지 않고 embed 요청에도 설치 식별자를 명시함.
            if is_embed_url(info.requestUrl().toString(), engine.video_id):
                info.setHttpHeader(b"Referer", APP_ORIGIN.encode("ascii"))

    class Page(QWebEnginePage):
        def acceptNavigationRequest(self, url, kind, main):
            if engine.closed:
                return False
            text = url.toString()
            if main and engine.loading_wrapper and (text.startswith("data:text/html") or text == APP_ORIGIN + "/"):
                engine.loading_wrapper = False
                return True
            if kind == self.NavigationType.NavigationTypeLinkClicked:
                if external_video_link(text):
                    open_url(text)
                return False
            if not main and is_playback_frame(text, engine.video_id):
                return True
            return False

        def chooseFiles(self, *args):
            return []

        def javaScriptConfirm(self, *args):
            return False

        def javaScriptAlert(self, *args):
            pass

        def javaScriptPrompt(self, *args):
            return False, ""

    class Engine(QObject):
        def __init__(self):
            super().__init__(parent)
            self.closed, self.loading_wrapper = False, False
            self.video_id, self.last_event, self.pending = "___________", None, False
            self.widget = QWebEngineView(parent)
            self.widget.setMinimumSize(200, 200)
            self.widget.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
            # 이름 없는 프로필은 디스크에 기록하지 않음. 페이지를 먼저 해제함.
            self.profile = QWebEngineProfile()
            self.profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.MemoryHttpCache)
            self.profile.setHttpCacheMaximumSize(16 * 1024 * 1024)
            self.profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.NoPersistentCookies)
            if hasattr(self.profile, "setPersistentPermissionsPolicy"):
                self.profile.setPersistentPermissionsPolicy(QWebEngineProfile.PersistentPermissionsPolicy.AskEveryTime)
            self.page = Page(self.profile, self.widget)
            self.page.destroyed.connect(self.profile.deleteLater)
            self.widget.setPage(self.page)
            self.interceptor = Referrer(self.profile)
            self.profile.setUrlRequestInterceptor(self.interceptor)
            settings = self.page.settings()
            for name, value in (("FullScreenSupportEnabled", True), ("PlaybackRequiresUserGesture", False),
                                ("JavascriptCanOpenWindows", False), ("JavascriptCanAccessClipboard", False),
                                ("LocalContentCanAccessFileUrls", False), ("LocalContentCanAccessRemoteUrls", False)):
                settings.setAttribute(getattr(QWebEngineSettings.WebAttribute, name), value)
            self.profile.downloadRequested.connect(lambda request: request.cancel())
            self.page.featurePermissionRequested.connect(
                lambda origin, feature: self.page.setFeaturePermission(
                    origin, feature, QWebEnginePage.PermissionPolicy.PermissionDeniedByUser))
            if hasattr(self.page, "permissionRequested"):
                self.page.permissionRequested.connect(lambda request: request.deny())
            if hasattr(self.page, "fileSystemAccessRequested"):
                self.page.fileSystemAccessRequested.connect(lambda request: request.reject())
            self.page.newWindowRequested.connect(self.new_window)
            self.page.fullScreenRequested.connect(self.fullscreen)
            self.page.loadFinished.connect(self.loaded)
            self.page.renderProcessTerminated.connect(lambda *_: self.emit("error", 5))
            self.poll_timer = QTimer(self)
            self.poll_timer.setInterval(300)
            self.poll_timer.timeout.connect(self.poll)
            self.deadline = QTimer(self)
            self.deadline.setSingleShot(True)
            self.deadline.timeout.connect(lambda: self.emit("error", 0))

        def emit(self, kind, code=None):
            if not self.closed:
                on_event(kind, code)

        def start(self, video_id):
            self.video_id = checked_video_id(video_id)
            self.loading_wrapper = True
            from PyQt6.QtCore import QUrl
            self.page.setHtml(player_html(video_id), QUrl(APP_ORIGIN + "/"))
            self.poll_timer.start()
            self.deadline.start(PLAYER_TIMEOUT_MS)

        def loaded(self, ok):
            if not ok:
                self.emit("error", 0)

        def poll(self):
            if not self.closed and not self.pending:
                self.pending = True
                flag = "true" if parent.can_autoplay() else "false"
                self.page.runJavaScript(f"window.tryRokeyPlayback?.({flag}); window.rokeyState || null", self.received)

        def received(self, value):
            self.pending = False
            if self.closed or not isinstance(value, dict) or value == self.last_event:
                return
            self.last_event = value
            kind = value.get("kind")
            if kind in ("ready", "state", "blocked", "error"):
                self.deadline.stop()
                # 같은 조회 주기 안에서 재생이나 차단을 거친 오류도 늦은 오류로 전달함.
                if kind == "error" and value.get("initial") is False:
                    kind = "late_error"
                self.emit(kind, value.get("code"))

        def new_window(self, request):
            url = request.requestedUrl().toString()
            if not self.closed and request.isUserInitiated() and external_video_link(url):
                open_url(url)

        def fullscreen(self, request):
            if not self.closed and request.origin().host() in (EMBED_HOST, "rokey.python.study"):
                request.accept()
                self.emit("fullscreen", request.toggleOn())
            else:
                request.reject()

        def exit_fullscreen(self):
            if not self.closed:
                self.page.runJavaScript("if (document.fullscreenElement) document.exitFullscreen()")

        def close(self):
            if self.closed:
                return
            self.closed = True
            self.poll_timer.stop()
            self.deadline.stop()
            self.page.setAudioMuted(True)
            self.widget.stop()
            self.page.runJavaScript("window.stopRokeyVideo && window.stopRokeyVideo()")
            self.page.setVisible(False)
            self.page.setLifecycleState(QWebEnginePage.LifecycleState.Discarded)
            self.widget.hide()
            self.widget.deleteLater()
            self.deleteLater()

    engine = Engine()
    return engine


class VideoDialog(QDialog):
    """on_prepare(done)는 취소 함수를 반환할 수 있음. 화면 스레드의 done(result)는 반영 여부를 반환함."""

    state_changed = pyqtSignal(str)

    def __init__(self, parent, video, open_url, on_prepare=None, engine_factory=None):
        super().__init__(parent)
        self.video_id = checked_video_id(video.video_id)
        self.video, self.open_url, self.on_prepare = video, open_url, on_prepare
        self.engine_factory = engine_factory or create_engine
        self.engine, self.cancel_prepare = None, None
        self.state, self.generation, self.closed = "idle", 0, False
        self._embed_fallback_until = 0
        self._fullscreen, self._changing_window = False, False
        self._starting_engine, self._document_hidden = False, False
        self.setWindowTitle("영상 보기")
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.shell = DialogLayout(self, "영상 보기")
        self.title = kit.para(video.title, "headline", bold=True)
        self.author = kit.para(video.author, "caption", "secondary")
        self.status = kit.para("")
        self.surface = VideoSurface(self)
        self.surface.hide()
        self.privacy = kit.para("이 창에서는 YouTube 쿠키와 캐시를 메모리에만 보관합니다.", "caption", "secondary")
        self.size_note = kit.para("영상 영역이 작습니다. 창을 넓히거나 YouTube에서 열어 주세요.", "caption", "secondary")
        self.size_note.hide()
        for widget in (self.title, self.author, self.status, self.surface, self.size_note, self.privacy):
            self.shell.content.addWidget(widget)
        self.prepare_button = kit.button("앱 내 재생기 설치", "primary", "l")
        self.retry_button = kit.button("다시 재생", "primary", "l")
        self.stop_button = kit.button("재생 멈추기", "secondary", "l")
        self.source_button = kit.button("YouTube에서 열기", "secondary", "l")
        self.close_button = kit.button("닫기", "secondary", "l")
        for button in (self.prepare_button, self.retry_button, self.stop_button, self.source_button, self.close_button):
            button.setAutoDefault(False)
            button.setDefault(False)
        self.shell.actions.set_actions([self.source_button], [self.close_button, self.stop_button,
                                                               self.prepare_button, self.retry_button])
        self.prepare_button.clicked.connect(self.prepare)
        self.retry_button.clicked.connect(self.play)
        self.stop_button.clicked.connect(self.stop)
        self.source_button.clicked.connect(lambda: self._external(watch_url(self.video_id)))
        self.close_button.clicked.connect(self.close)
        self.shell.scroll.viewport().installEventFilter(self)
        self._buttons()

    def _buttons(self):
        self.prepare_button.setVisible(self.state == "unavailable" and self.on_prepare is not None)
        self.retry_button.setVisible(self.state in ("stopped", "ended", "error"))
        self.stop_button.setVisible(self.engine is not None)
        self.close_button.setText("설치 취소하고 닫기" if self.state == "preparing" else "닫기")
        for button in (self.prepare_button, self.retry_button, self.stop_button, self.source_button, self.close_button):
            button.setMinimumWidth(0)
            button.ensurePolished()
            button.setMinimumWidth(button.sizeHint().width())
        self.shell.actions.invalidate()

    def refont(self):
        self._buttons()
        self.shell.content.invalidate()

    def _state(self, state, message):
        self.state = state
        self.status.setText(message)
        self._buttons()
        self.state_changed.emit(state)

    def open(self):
        if not self.closed and self.state == "idle":
            self.shell.fit(1000, 680)
            self._place()
            self.play()

    def _place(self):
        room = self.screen().availableGeometry()
        owner = self.parentWidget()
        rect = self.frameGeometry()
        rect.moveCenter(owner.frameGeometry().center() if owner is not None else room.center())
        self.move(max(room.left(), min(rect.left(), room.right() - rect.width() + 1)),
                  max(room.top(), min(rect.top(), room.bottom() - rect.height() + 1)))

    def play(self):
        if self.closed or self.state not in ("idle", "error", "stopped", "ended"):
            return
        self._embed_fallback_until = monotonic() + PLAYER_TIMEOUT_MS / 1000 if self.state == "idle" else 0
        self._release()
        current = self.generation
        self._state("requesting", "영상을 불러오고 있습니다.")
        if self.closed or self.generation != current:
            return
        if getattr(self.video, "embeddable", None) is False:
            self._external(watch_url(self.video_id))
            return
        if self.width() - 64 < 200:
            self._external(watch_url(self.video_id), "stopped", "앱에서 보려면 창을 넓혀 주세요.")
            return

        def open_link(url):
            if self.generation == current:
                self._external(url)

        try:
            engine = self.engine_factory(self.surface, lambda kind, code=None: self._event(current, kind, code), open_link)
            if self.closed or self.generation != current:
                engine.close()
                return
            self.engine = engine
            self.surface.box.addWidget(engine.widget)
            self.surface.show()
            self._buttons()
            if not self.isVisible():
                super().open()
            if self.closed or self.generation != current:
                return
            self.shell.scroll.ensureWidgetVisible(self.surface, 0, 0)
            # Windows에서 첫 문서를 붙일 때의 창 재생성을 사용자 숨김과 구분함.
            self._document_hidden = False
            self._starting_engine = True
            try:
                engine.start(self.video_id)
            finally:
                self._starting_engine = False
                if self._document_hidden and not self.closed and self.engine is engine:
                    self._document_hidden = False
                    self.show()
        except EngineUnavailable as error:
            if self.generation == current:
                self._external(watch_url(self.video_id), error.state, str(error))
        except (ImportError, OSError, RuntimeError):
            if self.generation == current:
                self._external(watch_url(self.video_id), "error", "앱 내 재생기를 열지 못했습니다.")

    def _event(self, generation, kind, code=None):
        if self.closed or generation != self.generation:
            return
        if kind == "blocked" or (kind == "state" and code in (0, 1, 2)):
            self._embed_fallback_until = 0
        if kind == "error" and code in (101, 150) and monotonic() < self._embed_fallback_until and self.isVisible():
            self._embed_fallback_until = 0
            self._external(watch_url(self.video_id), "error", error_message(code))
            return
        if kind == "fullscreen":
            self._set_fullscreen(bool(code))
        elif kind in ("error", "late_error"):
            self._release()
            self._state("error", error_message(code))
        elif kind == "blocked":
            self._state("ready", "자동 재생이 차단되었습니다. 영상의 재생 버튼을 눌러 주세요.")
        elif kind == "ready":
            self._state("ready", "영상의 재생 버튼을 눌러 주세요.")
        elif kind == "state":
            state, message = {
                -1: ("ready", "영상의 재생 버튼을 눌러 주세요."),
                0: ("ended", "영상 재생이 끝났습니다."),
                1: ("playing", "영상을 재생하고 있습니다."),
                2: ("paused", "영상이 일시 정지했습니다."),
                3: ("buffering", "영상 내용을 불러오고 있습니다."),
                5: ("ready", "영상의 재생 버튼을 눌러 주세요."),
            }.get(code, (None, ""))
            if state:
                if state == "ended":
                    self._release()
                self._state(state, message)

    def prepare(self):
        if self.closed or self.state != "unavailable" or self.on_prepare is None:
            return
        self.generation += 1
        current = self.generation
        self._state("preparing", "앱 내 재생기를 설치하고 있습니다.")
        if self.closed or self.generation != current:
            return

        def done(result):
            if self.closed or self.generation != current or self.state != "preparing":
                return False
            self.cancel_prepare = None
            if result.get("ok"):
                self._state("restart", "앱 내 재생기를 설치했습니다. 프로그램을 다시 시작해 주세요.")
            elif result.get("status") == "cancelled":
                self._state("unavailable", "설치를 취소했습니다.")
            else:
                self._state("unavailable", result.get("message") or "앱 내 재생기를 설치하지 못했습니다.")
            return not self.closed and self.generation == current
        try:
            cancel = self.on_prepare(done)
            if self.state == "preparing" and not self.closed:
                self.cancel_prepare = cancel if callable(cancel) else None
            elif self.closed and callable(cancel):
                cancel()
        except (OSError, RuntimeError):
            done({"ok": False})

    def _release(self):
        self.generation += 1
        engine, self.engine = self.engine, None
        self._set_fullscreen(False)
        if engine is not None:
            self.surface.box.removeWidget(engine.widget)
            engine.close()
        self.surface.hide()

    def stop(self):
        if self.closed:
            return
        self._release()
        self._cancel_preparation()
        self._state("stopped", "영상 재생을 멈췄습니다.")

    def _cancel_preparation(self):
        cancel, self.cancel_prepare = self.cancel_prepare, None
        if cancel is not None:
            try:
                cancel()
            except (OSError, RuntimeError):
                pass

    def _external(self, url, failure_state="error", reason=""):
        if self.closed or not external_video_link(url):
            return
        self._release()
        self._cancel_preparation()
        current = self.generation
        try:
            opened = self.open_url(url)
        except (OSError, RuntimeError):
            opened = False
        if self.closed or self.generation != current:
            return
        if opened is False:
            self._state(failure_state, ("기본 브라우저를 열지 못했습니다. " + reason).strip())
            if not self.closed and self.generation == current and not self.isVisible():
                super().open()
        else:
            self.accept()

    def _set_fullscreen(self, enabled):
        if enabled == self._fullscreen:
            return
        self._fullscreen = enabled
        if enabled:
            self._normal_geometry = self.saveGeometry()
        self.surface.fullscreen = enabled
        for widget in (self.shell.header, self.shell.footer, self.title, self.author, self.status, self.privacy):
            widget.setVisible(not enabled)
        self.size_note.hide()
        self.shell.content.setContentsMargins(*( (0, 0, 0, 0) if enabled else (32, 8, 32, 24)))
        self.surface.setSizePolicy(QSizePolicy.Policy.Expanding,
                                   QSizePolicy.Policy.Expanding if enabled else QSizePolicy.Policy.Preferred)
        self._changing_window = True
        try:
            if enabled:
                self.showFullScreen()
            else:
                if self.isVisible() and not self.closed:
                    self.showNormal()
                else:
                    self.setWindowState(self.windowState() & ~Qt.WindowState.WindowFullScreen)
                self.restoreGeometry(self._normal_geometry)
        finally:
            self._changing_window = False

    def keyPressEvent(self, event):
        if self._fullscreen and event.key() == Qt.Key.Key_Escape:
            if self.engine is not None:
                self.engine.exit_fullscreen()
            self._set_fullscreen(False)
            return
        super().keyPressEvent(event)

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.Resize and self.engine is not None and not self._fullscreen:
            small = self.shell.scroll.viewport().width() - 64 < 200
            self.size_note.setVisible(small)
            if small:
                self.stop()
        return super().eventFilter(watched, event)

    def hideEvent(self, event):
        if not self.closed and not self._changing_window:
            if self._starting_engine:
                self._document_hidden = True
            else:
                self.stop()
        super().hideEvent(event)

    def done(self, result):
        self._shutdown()
        super().done(result)

    def close(self):
        self._shutdown()
        return super().close()

    def closeEvent(self, event):
        self._shutdown()
        super().closeEvent(event)

    def _shutdown(self):
        if not self.closed:
            self.closed = True
            self._cancel_preparation()
            self._release()
            self._state("closed", "영상 창을 닫았습니다.")
