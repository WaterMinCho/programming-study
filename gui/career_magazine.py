"""영상·논문을 오프라인으로 탐색하며 명시한 재생 요청만 외부 뷰어에 전달함."""
from functools import partial
from urllib.parse import urlsplit

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QComboBox, QDialog, QLineEdit, QSizePolicy, QWidget

from career.catalog import load_catalog
from gui import kit, theme
from gui.career_gallery import VideoCard, VideoFilters, VideoGallery
from gui.career_paper_preview import PaperPreview
from gui.career_roadmap import ReadingPage, flow_buttons
from gui.dialog_layout import DialogLayout
from gui.paper_explainer import load_explanations


class SourceDetails(QWidget):
    """출처 설명을 접어 두고 펼칠 때 현재 문단 위치를 보존함."""
    def __init__(self, owner, title="출처·검토 범위"):
        super().__init__()
        self.owner = owner
        self.title = title
        box = kit.box(self, spacing=12)
        self.button = kit.button(title + " 펼치기", "text")
        self.button.setProperty("reading_anchor", True)
        self.button.setCheckable(True)
        box.addWidget(flow_buttons(self.button))
        self.content = QWidget()
        self.body = kit.box(self.content, spacing=12)
        box.addWidget(self.content)
        self.content.hide()
        self.button.toggled.connect(self.toggle)

    def toggle(self, opened):
        self.owner._remember()
        self.content.setVisible(opened)
        self.button.setText(self.title + (" 접기" if opened else " 펼치기"))
        self.owner._schedule_restore()


class CareerMagazinePage(ReadingPage):
    video_requested = pyqtSignal(object)
    stop_requested = pyqtSignal()
    paper_requested = pyqtSignal(object)
    figure_requested = pyqtSignal(object)

    def __init__(self, parent=None, *, catalog=None, on_back=None, on_video=None, on_stop=None,
                 on_paper=None, on_source=None, on_figure=None):
        super().__init__(parent, on_back, back_label="← 개발자 로드맵")
        self.catalog = catalog if catalog is not None else load_catalog()
        self.on_video, self.on_stop, self.on_paper, self.on_source = on_video, on_stop, on_paper, on_source
        self.on_figure = on_figure
        self.selected_video_id = self.catalog.videos[0].video_id if self.catalog.videos else None
        self.online = None
        self.playback_state = "idle"
        self._requested_id = None
        self._tab_anchors = {}
        title = kit.para("매거진", "title")
        title.setProperty("reading_anchor", True)
        header = QWidget()
        heading = kit.box(header, spacing=theme.GAP["paragraph"], horizontal=True)
        heading.addWidget(title)
        heading.addStretch(1)
        self.tabs = kit.TabBar(["영상", "논문 해설"])
        self.tabs.setAccessibleName("매거진 자료 종류")
        self.tabs.picked.connect(self._change_tab)
        heading.addWidget(self.tabs)
        self.body.addWidget(header)
        self.body.addSpacing(theme.GAP["paragraph"])

        self.video_content = QWidget()
        self.video_box = kit.box(self.video_content, spacing=theme.GAP["paragraph"])
        self.body.addWidget(self.video_content)
        self.search = kit.typed(QLineEdit(), "body")
        self.search.setPlaceholderText("제목·제작자·주제 검색")
        self.search.setAccessibleName("영상 검색")
        self.search.setClearButtonEnabled(True)
        self.origin = kit.typed(QComboBox(), "body")
        self.origin.setAccessibleName("영상 목록 범위")
        for text, key in (("모든 영상", None), ("스터디 선정", "selected"), ("추가 자료", "additional")):
            self.origin.addItem(text, key)
        self.video_box.addWidget(VideoFilters(self.search, self.origin))
        self.network_note = kit.para("", "caption", "secondary")
        self.video_box.addWidget(self.network_note)
        self.network_note.hide()
        self.gallery = VideoGallery()
        self.video_box.addWidget(self.gallery)
        self.empty_note = kit.para("", "body", "secondary")
        self.video_box.addWidget(self.empty_note)
        self._extra_video_id = None
        self.cards = {}
        for video in self.catalog.videos:
            card = VideoCard(video)
            card.cover.clicked.connect(partial(self._activate, video.video_id))
            card.info.clicked.connect(partial(self._show_info, video, card.info))
            self.cards[video.video_id] = card
        self.search.textChanged.connect(lambda _: self._filter())
        self.origin.currentIndexChanged.connect(lambda _: self._filter())

        # 별도 재생 위젯을 제공하는 호출자에게만 재생 영역을 표시함.
        self.viewer_host, self.viewer_layout = kit.card(pad=16, spacing=12)
        self._viewer = None
        self.viewer_host.setAccessibleName("선택한 영상 재생 영역")
        self.play_button = kit.button("영상 재생", "primary")
        self.stop_button = kit.button("영상 정지")
        self.play_button.clicked.connect(self.play_video)
        self.stop_button.clicked.connect(self.stop_playback)
        self.viewer_layout.addWidget(flow_buttons(self.play_button, self.stop_button))
        self.playback_note = kit.para("", "caption", "secondary")
        self.viewer_layout.addWidget(self.playback_note)
        self.video_box.addWidget(self.viewer_host)
        self.viewer_host.hide()
        self.info_dialog = None
        self.paper_content = QWidget()
        self.paper_box = kit.box(self.paper_content, spacing=24)
        self.body.addWidget(self.paper_content)
        self.body.addStretch(1)
        self.paper_content.hide()
        self._show_papers()
        self._filter()
        self._update_actions()

    def set_viewer(self, widget):
        """부모가 만든 재생 위젯을 붙임. URL을 설정하거나 재생을 시작하지 않음."""
        if self._viewer is widget:
            return
        if self._viewer is not None:
            self.viewer_layout.removeWidget(self._viewer)
            self._viewer.hide()
            self._viewer.deleteLater()
        self._viewer = widget
        self.viewer_layout.insertWidget(0, widget)
        self.viewer_host.show()
        widget.setMinimumWidth(0)
        widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    def video(self):
        return next((row for row in self.catalog.videos if row.video_id == self.selected_video_id), None)

    def _filter(self, *, related_id=None):
        self._anchor = None
        query, origin = self.search.text().strip().casefold(), self.origin.currentData()
        self.rows = {v.video_id: self.cards[v.video_id] for v in self.catalog.videos
                     if (not origin or v.origin == origin)
                     and (not query or query in f"{v.title} {v.author} {v.topic}".casefold())}
        if self._extra_video_id:
            self.cards[self._extra_video_id].related_note.hide()
        self._extra_video_id = None
        if related_id is not None and related_id not in self.rows:
            self._extra_video_id = related_id
            card = self.cards[related_id]
            card.related_note.show()
            self.rows = {related_id: card, **self.rows}
        self.gallery.set_cards(self.rows.values())
        self.gallery.setVisible(bool(self.rows))
        self.empty_note.setVisible(not self.rows)
        if not self.rows:
            state = self.catalog.states["videos"]
            text = {"empty": "공개한 영상 목록이 없습니다.", "unavailable": "영상 목록 파일이 없습니다. 프로그램을 업데이트한 뒤 다시 열어 주세요.",
                    "invalid": "영상 목록을 읽지 못했습니다. 프로그램을 업데이트한 뒤 다시 열어 주세요."}.get(state, "검색 조건에 맞는 영상이 없습니다.")
            self.empty_note.setText(text)

    def select_video(self, video_id, *, reveal=False):
        """영상을 선택함. 로드맵에서 들어오면 검색 조건을 유지하고 해당 표지에 초점을 맞춤."""
        if video_id not in self.cards:
            return False
        if video_id != self.selected_video_id:
            self.stop_playback()
            if self.selected_video_id is not None:
                previous = self.cards[self.selected_video_id]
                previous.cover.setChecked(False)
                previous.error.hide()
            self.selected_video_id = video_id
            self.playback_state = "idle"
            self.playback_note.setText("")
            self._update_actions()
        self.cards[video_id].cover.setChecked(True)
        if reveal:
            if video_id not in self.rows or (self._extra_video_id and self._extra_video_id != video_id):
                self._filter(related_id=video_id)
            card = self.cards[video_id]
            target = card.cover if card.cover.isEnabled() else card.info
            target.setFocus(Qt.FocusReason.OtherFocusReason)
            self._anchor = card, theme.GAP["detail"]
            self._schedule_restore()
        return True

    def _activate(self, video_id, checked=False):
        if self.select_video(video_id):
            self.play_video()

    def _show_info(self, video, trigger=None, checked=False):
        if self.info_dialog is not None:
            return
        dialog = QDialog(self)
        self.info_dialog = dialog
        dialog.setWindowTitle("영상 정보")
        shell = DialogLayout(dialog, "영상 정보")
        shell.content.addWidget(kit.heading(kit.para(video.title, "headline"),
                                            kit.para(f"{video.author} · {video.date_label} · {video.duration_label}",
                                                     "caption", "secondary")))
        visual = {"not_reviewed": "시각 장면 미검토", "visual_scenes_not_reviewed": "시각 장면 미검토",
                  "selected_scenes_reviewed": "일부 시각 장면 확인"}.get(video.visual_review, "시각 장면 검토 범위 미확인")
        for title, text in (("영상 내용", video.summary), ("함께 해볼 것", video.learning_use),
                            ("확인한 범위", video.limitations)):
            shell.content.addWidget(kit.heading(kit.para(title, "label", bold=True), kit.para(text)))
        shell.content.addWidget(kit.para(f"{video.review_label} · {visual} · 확인일 {video.checked_date}",
                                        "caption", "secondary"))
        shell.content.addWidget(kit.para("출처", "label", bold=True))
        for url in dict.fromkeys((video.url, *video.source_urls)):
            label = "YouTube 원본" if url == video.url else urlsplit(url).hostname
            if self.on_source:
                button = kit.button(label, "text", "s")
                button.setToolTip(url)
                button.setAccessibleDescription(url)
                button.setEnabled(self.online is not False)
                button.clicked.connect(lambda checked=False, link=url: self._open_source(link))
                shell.content.addWidget(button, 0, Qt.AlignmentFlag.AlignLeft)
            else:
                shell.content.addWidget(kit.para(url, "caption", "secondary"))
        close = kit.button("닫기")
        close.clicked.connect(dialog.accept)
        shell.actions.set_actions([], [close])
        shell.fit(640)
        dialog.finished.connect(partial(self._info_closed, trigger))
        dialog.open()
        close.setFocus()

    def _info_closed(self, button, result):
        self.info_dialog.deleteLater()
        self.info_dialog = None
        if button is not None and button.isVisibleTo(self.content):
            button.setFocus(Qt.FocusReason.OtherFocusReason)

    def _open_source(self, url):
        if self.on_source and self.online is not False:
            self.on_source(url)

    def play_video(self):
        video = self.video()
        if video is None or not self.on_video or not self.on_stop or self.online is False or self._requested_id == video.video_id:
            return
        self.cards[video.video_id].cover.setChecked(True)
        self.cards[video.video_id].error.hide()
        self._requested_id = video.video_id
        self.playback_state = "requested"
        self.playback_note.setText("영상 열기를 요청했습니다.")
        self._update_actions()
        try:
            self.on_video(video)
            self.video_requested.emit(video)
        except Exception:
            self._requested_id = None
            self.playback_state = "error"
            self._show_error("영상을 열지 못했습니다. 다시 시도하거나 영상 정보에서 원본을 열어 주세요.")
            self._update_actions()

    def _show_error(self, message):
        self.playback_note.setText(message)
        error = self.cards[self.selected_video_id].error
        error.setText(message)
        error.show()

    def stop_playback(self):
        if self._requested_id is None:
            return
        self._requested_id = None
        self.playback_state = "stopped"
        self.playback_note.setText("영상 정지를 요청했습니다.")
        try:
            if self.on_stop:
                self.on_stop()
            self.stop_requested.emit()
        except Exception:
            self.playback_state = "error"
            self._show_error("정지 여부를 확인하지 못했습니다. 재생 화면을 확인해 주세요.")
        self._update_actions()

    def set_playback_state(self, video_id, state, message=""):
        """현재 요청과 같은 영상의 실제 뷰어 상태만 반영함."""
        if video_id != self._requested_id or video_id != self.selected_video_id:
            return False
        labels = {"playing": "영상을 재생하고 있습니다.", "paused": "영상이 일시 정지했습니다.",
                  "ended": "영상 재생이 끝났습니다.", "error": "영상을 재생하지 못했습니다. YouTube 원본에서 확인해 주세요."}
        if state not in labels:
            return False
        self.playback_state = state
        if state == "error":
            self._show_error((message or "").strip() or labels[state])
        else:
            self.playback_note.setText(labels[state] + ("\n" + message if message else ""))
            self.cards[video_id].error.hide()
        if state in ("ended", "error"):
            self._requested_id = None
        self._update_actions()
        return True

    def set_online(self, online):
        """부모가 확인한 연결 상태를 받음. 이 화면은 통신 검사를 하지 않음."""
        self.online = online
        if online is False:
            self.stop_playback()
        self.network_note.setText("오프라인입니다. 인터넷에 연결하면 영상을 재생할 수 있습니다.")
        self.network_note.setVisible(online is False)
        self._update_actions()

    def _update_actions(self):
        available = bool(self.on_video and self.on_stop and self.online is not False)
        self.play_button.setEnabled(bool(self.video() and available and not self._requested_id))
        self.stop_button.setEnabled(self._requested_id is not None)
        for card in self.cards.values():
            card.cover.setEnabled(available)

    def open_source(self):
        video = self.video()
        if video:
            self._open_source(video.url)

    def _restore(self):
        # 열이 바뀔 때 같은 줄의 다른 표지를 임시 기준으로 삼지 않도록 기존 표지를 유지함.
        anchor = self._anchor
        super()._restore()
        if anchor and not self._settling and isinstance(anchor[0], VideoCard) and anchor[0].isVisibleTo(self.content):
            self._anchor = anchor

    def _change_tab(self, number):
        previous = 0 if self.video_content.isVisibleTo(self.content) else 1
        self._remember()
        self._tab_anchors[previous] = self._anchor
        if number == 1:
            self.stop_playback()
        self.video_content.setVisible(number == 0)
        self.paper_content.setVisible(number == 1)
        self.tabs.set_current(number)
        self._anchor = self._tab_anchors.get(number)
        if self._anchor is not None:
            self._schedule_restore()
        else:
            self.scroll.verticalScrollBar().setValue(0)

    def _show_papers(self):
        state = self.catalog.states["papers"]
        self.paper_box.addWidget(kit.heading(kit.para("논문 해설", "headline"), kit.para("어떤 문제를 풀려는 논문인지 읽고, 그림으로 계산 과정을 따라가세요.")))
        if state != "ready":
            text = {"unavailable": "논문 해설 자료는 아직 제공하지 않습니다.", "empty": "공개한 논문 해설이 없습니다.",
                    "invalid": "논문 해설 자료를 읽지 못했습니다. 프로그램을 업데이트한 뒤 다시 열어 주세요."}[state]
            self.paper_box.addWidget(kit.para(text, "body", "secondary"))
        try:
            explanations = load_explanations() if self.catalog.papers else {}
        except (OSError, UnicodeError, ValueError, KeyError, TypeError, AttributeError):
            explanations = {}
        self.paper_previews = {}
        for paper in self.catalog.papers:
            section, box = kit.card(pad=24, spacing=24)
            section.setProperty("reading_anchor", True)
            explanation = explanations.get(paper.paper_id)
            preview = PaperPreview(paper, explanation)
            self.paper_previews[paper.paper_id] = preview
            preview.setProperty("reading_anchor", True)
            preview.setEnabled(bool(self.on_figure and paper.figure_description))
            preview.clicked.connect(lambda checked=False, item=paper: self.open_figure(item))
            title = explanation["short_title"] if explanation else paper.title.split(":", 1)[0]
            step = explanation["steps"][preview.stage] if explanation else None
            question = step["question"] if step else paper.summary
            box.addWidget(kit.heading(kit.para(title, "headline"), kit.para(question)))
            box.addWidget(preview)
            if explanation:
                scope = QWidget()
                scope.setProperty("reading_anchor", True)
                scope_box = kit.box(scope, spacing=theme.GAP["detail"])
                scope_box.addWidget(kit.para(f"대표 단계 {preview.stage + 1} · " + step["title"], "caption", "secondary"))
                scope_box.addWidget(kit.para(step["shape"], "caption", "secondary"))
                scope_box.addWidget(kit.para(step["text"]))
                for text in (explanation["axes"], explanation["boundary"]):
                    scope_box.addWidget(kit.para(text, "caption", "secondary"))
                box.addWidget(scope)
            description = SourceDetails(self, "논문 설명·선행 개념")
            description.body.addWidget(kit.para(paper.summary))
            description.body.addWidget(kit.para(paper.beginner_explanation))
            description.body.addWidget(kit.para("읽기에 필요한 개념 · " + ", ".join(paper.prerequisites), "caption", "secondary"))
            details = SourceDetails(self)
            details.body.addWidget(kit.para(f"출처 · {paper.title}\n발표일 {paper.published_date or '미확인'}\n확인일 {paper.checked_date}", "caption", "secondary"))
            details.body.addWidget(kit.para(f"검토한 버전 {paper.examined_version or '미확인'}\n{paper.verification_scope}", "caption", "secondary"))
            details.body.addWidget(kit.para(f"논문 이용 조건 · {paper.license_label}\n{paper.license_scope}", "caption", "secondary"))
            button = kit.button("논문 원문 열기", "text")
            button.setToolTip(paper.url)
            button.setAccessibleDescription(paper.url)
            button.clicked.connect(lambda checked=False, item=paper: self.open_paper(item))
            figure = kit.button("그림 설명 보기")
            figure.clicked.connect(lambda checked=False, item=paper: self.open_figure(item))
            license_button = kit.button("이용 조건 원문", "text")
            license_button.setToolTip(paper.license_url)
            license_button.clicked.connect(lambda checked=False, url=paper.license_url: self.on_source(url))
            details.body.addWidget(flow_buttons(license_button))
            details.body.addWidget(flow_buttons(button))
            box.addWidget(flow_buttons(figure))
            button.setVisible(self.on_paper is not None)
            figure.setVisible(bool(self.on_figure and paper.figure_description))
            license_button.setVisible(bool(self.on_source and paper.license_url))
            box.addWidget(description)
            box.addWidget(details)
            self.paper_box.addWidget(section)

    def open_paper(self, paper):
        if self.on_paper:
            self.on_paper(paper)
            self.paper_requested.emit(paper)

    def open_figure(self, paper):
        if self.on_figure and paper.figure_description:
            self.on_figure(paper)
            self.figure_requested.emit(paper)

    def hideEvent(self, event):
        self.stop_playback()
        super().hideEvent(event)


MagazinePage = CareerMagazinePage
