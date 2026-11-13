"""영상·논문을 오프라인으로 탐색하며 명시한 재생 요청만 외부 뷰어에 전달함."""
from PyQt6.QtCore import QTimer, pyqtSignal
from PyQt6.QtWidgets import QComboBox, QLineEdit, QSizePolicy, QWidget

from career.catalog import load_catalog
from gui import kit, theme
from gui.career_roadmap import ReadingPage, clear_layout, flow_buttons


class SourceDetails(QWidget):
    """출처 설명을 접어 두고 펼칠 때 현재 문단 위치를 보존함."""
    def __init__(self, owner):
        super().__init__()
        self.owner = owner
        box = kit.box(self, spacing=12)
        self.button = kit.button("출처·검토 범위 펼치기", "text")
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
        self.button.setText("출처·검토 범위 접기" if opened else "출처·검토 범위 펼치기")
        self.owner._schedule_restore()


class CareerMagazinePage(ReadingPage):
    video_requested = pyqtSignal(object)
    stop_requested = pyqtSignal()
    paper_requested = pyqtSignal(object)
    figure_requested = pyqtSignal(object)

    def __init__(self, parent=None, *, catalog=None, on_back=None, on_video=None, on_stop=None,
                 on_paper=None, on_source=None, on_figure=None):
        super().__init__(parent, on_back)
        self.catalog = catalog if catalog is not None else load_catalog()
        self.on_video, self.on_stop, self.on_paper, self.on_source = on_video, on_stop, on_paper, on_source
        self.on_figure = on_figure
        self.selected_video_id = None
        self.online = None
        self.playback_state = "idle"
        self._requested_id = None
        self._tab_anchors = {}
        title = kit.para("매거진", "title")
        title.setProperty("reading_anchor", True)
        self.body.addWidget(kit.heading(title, kit.para("개발자의 일과 기술을 영상으로 살펴보세요. 배운 개념을 더 알아보고 싶을 때 논문 해설도 읽을 수 있습니다.")))
        self.body.addSpacing(24)
        self.tabs = kit.TabBar(["영상", "논문 해설"])
        self.tabs.setAccessibleName("매거진 자료 종류")
        self.tabs.picked.connect(self._change_tab)
        self.body.addWidget(self.tabs)
        self.body.addSpacing(24)
        self.video_content = QWidget()
        self.video_box = kit.box(self.video_content, spacing=24)
        self.body.addWidget(self.video_content)
        self.network_note = kit.para("목록·설명은 오프라인에서도 읽을 수 있습니다. 영상 재생에는 인터넷 연결이 필요합니다.", "caption", "secondary")
        self.video_box.addWidget(self.network_note)
        self.detail, detail_box = kit.card(pad=24, spacing=24)
        self.detail.setProperty("reading_anchor", True)
        self.video_box.addWidget(self.detail)
        self.video_title = kit.para("영상을 골라 보세요.", "headline")
        self.metadata = kit.para("", "caption", "secondary")
        detail_box.addWidget(kit.heading(self.video_title, self.metadata))
        self.viewer_host = kit.frame("well")
        self.viewer_host.setAccessibleName("선택한 영상 재생 영역")
        self.viewer_host.setMinimumWidth(0)
        self.viewer_host.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.viewer_layout = kit.box(self.viewer_host, (16, 16, 16, 16), 16)
        self.viewer_placeholder = kit.para("[영상 재생]을 누르면 선택한 영상을 엽니다.", "body", "secondary")
        self.viewer_layout.addWidget(self.viewer_placeholder)
        detail_box.addWidget(self.viewer_host)
        self.play_button = kit.button("영상 재생", "primary")
        self.stop_button = kit.button("영상 정지")
        self.source_button = kit.button("YouTube 원본 열기", "text")
        self.play_button.clicked.connect(self.play_video)
        self.stop_button.clicked.connect(self.stop_playback)
        self.source_button.clicked.connect(self.open_source)
        detail_box.addWidget(flow_buttons(self.play_button, self.stop_button, self.source_button))
        self.playback_note = kit.para("재생 전입니다.", "caption", "secondary")
        detail_box.addWidget(self.playback_note)
        self.summary = kit.para("")
        self.summary.setProperty("reading_anchor", True)
        self.use = kit.para("")
        self.limitations = kit.para("", "caption", "secondary")
        detail_box.addWidget(kit.heading(kit.para("영상 내용", "body", bold=True), self.summary))
        detail_box.addWidget(kit.heading(kit.para("함께 해볼 것", "body", bold=True), self.use))
        self.source_details = SourceDetails(self)
        self.source_details.body.addWidget(self.limitations)
        detail_box.addWidget(self.source_details)
        self.list_heading = kit.para("업로드 날짜순 영상", "headline")
        self.list_heading.setProperty("reading_anchor", True)
        self.video_box.addSpacing(24)
        self.video_box.addWidget(kit.heading(self.list_heading, kit.para("최신 업로드부터 표시합니다. 날짜가 미확인인 영상은 마지막에 둡니다. 날짜 표시는 한국 시간입니다.", "caption", "secondary")))
        self.search = kit.typed(QLineEdit(), "body")
        self.search.setPlaceholderText("제목·제작자·주제로 찾기")
        self.search.setAccessibleName("영상 검색")
        self.video_box.addWidget(self.search)
        self.origin = kit.typed(QComboBox(), "body")
        self.origin.setMinimumHeight(theme.control_height("l"))
        self.origin.setAccessibleName("영상 목록 범위")
        for text, key in (("모든 영상", None), ("스터디 선정", "selected"), ("추가 자료", "additional")):
            self.origin.addItem(text, key)
        self.video_box.addWidget(self.origin)
        self.count = kit.para("", "caption", "secondary")
        self.video_box.addWidget(self.count)
        self.video_rows = QWidget()
        self.rows_layout = kit.box(self.video_rows, spacing=8)
        self.video_box.addWidget(self.video_rows)
        self.rows = {}
        self.search.textChanged.connect(self._filter)
        self.origin.currentIndexChanged.connect(self._filter)
        self.paper_content = QWidget()
        self.paper_box = kit.box(self.paper_content, spacing=24)
        self.body.addWidget(self.paper_content)
        self.paper_content.hide()
        self._show_papers()
        self._filter()
        if self.catalog.videos:
            self.select_video(self.catalog.videos[0].video_id, reveal=False)
        else:
            self.detail.hide()
        self._update_actions()

    def set_viewer(self, widget):
        """부모가 만든 재생 위젯을 붙임. URL을 설정하거나 재생을 시작하지 않음."""
        if self.viewer_layout.count() == 1 and self.viewer_layout.itemAt(0).widget() is widget:
            return
        clear_layout(self.viewer_layout)
        self.viewer_layout.addWidget(widget)
        widget.setMinimumWidth(0)
        widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    def video(self):
        return next((row for row in self.catalog.videos if row.video_id == self.selected_video_id), None)

    def _filter(self, *_):
        self._anchor = None
        clear_layout(self.rows_layout)
        self.rows = {}
        query, origin = self.search.text().strip().casefold(), self.origin.currentData()
        videos = [video for video in self.catalog.videos if (not origin or video.origin == origin)
                  and (not query or query in f"{video.title} {video.author} {video.topic}".casefold())]
        selected = sum(video.origin == "selected" for video in self.catalog.videos)
        additional = sum(video.origin == "additional" for video in self.catalog.videos)
        self.count.setText(f"{len(videos)}개 표시 · 스터디 선정 {selected}개 · 추가 자료 {additional}개")
        for video in videos:
            row = kit.Row(video.title, f"{video.author}\n{video.date_label} · {video.duration_label}", wrap=True)
            row.setProperty("reading_anchor", True)
            row.setProperty("picked", video.video_id == self.selected_video_id)
            row.setAccessibleName(f"{video.title}. {video.author}. {video.date_label}")
            row.clicked.connect(lambda vid=video.video_id: self.select_video(vid))
            self.rows[video.video_id] = row
            self.rows_layout.addWidget(row)
        if not videos:
            state = self.catalog.states["videos"]
            text = {"empty": "공개한 영상 목록이 없습니다.", "unavailable": "영상 목록 파일이 없습니다. 프로그램을 업데이트한 뒤 다시 열어 주세요.",
                    "invalid": "영상 목록을 읽지 못했습니다. 프로그램을 업데이트한 뒤 다시 열어 주세요."}.get(state, "검색 조건에 맞는 영상이 없습니다.")
            self.rows_layout.addWidget(kit.para(text))

    def select_video(self, video_id, *, reveal=True):
        video = next((row for row in self.catalog.videos if row.video_id == video_id), None)
        if video is None:
            return False
        if video_id == self.selected_video_id:
            return True
        self.stop_playback()
        self._anchor = None
        self.selected_video_id = video_id
        self.playback_state = "idle"
        self.video_title.setText(video.title)
        self.metadata.setText(f"{video.author}\n{video.date_label} · {video.duration_label}")
        self.summary.setText(video.summary)
        self.use.setText(video.learning_use)
        visual = {"not_reviewed": "시각 장면 미검토", "visual_scenes_not_reviewed": "시각 장면 미검토",
                  "selected_scenes_reviewed": "일부 시각 장면 확인"}.get(video.visual_review, "시각 장면 검토 범위 미확인")
        self.limitations.setText(f"{video.review_label} · {visual} · 확인일 {video.checked_date}\n{video.limitations}")
        self.playback_note.setText("재생 전입니다.")
        for vid, row in self.rows.items():
            row.setProperty("picked", vid == video_id)
            kit.repolish(row)
        self.detail.show()
        self._update_actions()
        if reveal:
            QTimer.singleShot(0, lambda: self.scroll.ensureWidgetVisible(self.detail, 0, 24))
        return True

    def play_video(self):
        video = self.video()
        if video is None or not self.on_video or not self.on_stop or self.online is False or self._requested_id == video.video_id:
            return
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
            self.playback_note.setText("영상을 열지 못했습니다. 다시 시도하거나 YouTube 원본을 열어 주세요.")
            self._update_actions()

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
            self.playback_note.setText("정지 여부를 확인하지 못했습니다. 재생 화면을 확인해 주세요.")
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
        self.playback_note.setText(labels[state] + ("\n" + message if message else ""))
        if state in ("ended", "error"):
            self._requested_id = None
        self._update_actions()
        return True

    def set_online(self, online):
        """부모가 확인한 연결 상태를 받음. 이 화면은 통신 검사를 하지 않음."""
        self.online = online
        if online is False:
            self.stop_playback()
        self.network_note.setText("오프라인입니다. 목록과 설명은 읽을 수 있습니다. 인터넷에 연결한 뒤 영상을 재생하세요." if online is False else
                                  "목록·설명은 오프라인에서도 읽을 수 있습니다. 영상 재생에는 인터넷 연결이 필요합니다.")
        self._update_actions()

    def _update_actions(self):
        video = self.video()
        self.play_button.setEnabled(bool(video and self.on_video and self.on_stop and self.online is not False and not self._requested_id))
        self.play_button.setToolTip("" if self.on_video and self.on_stop else "현재는 앱 안의 영상 재생을 사용할 수 없습니다.")
        self.stop_button.setEnabled(self._requested_id is not None)
        self.source_button.setVisible(self.on_source is not None)
        self.source_button.setEnabled(bool(video and self.online is not False))

    def open_source(self):
        video = self.video()
        if video and self.on_source and self.online is not False:
            self.on_source(video.url)

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
        self.paper_box.addWidget(kit.heading(kit.para("논문 해설", "headline"), kit.para("논문에서 다루는 문제와 입력·출력, 적용 조건을 초급 설명으로 연결합니다.")))
        if state != "ready":
            text = {"unavailable": "논문 해설 자료는 아직 제공하지 않습니다.", "empty": "공개한 논문 해설이 없습니다.",
                    "invalid": "논문 해설 자료를 읽지 못했습니다. 프로그램을 업데이트한 뒤 다시 열어 주세요."}[state]
            self.paper_box.addWidget(kit.para(text, "body", "secondary"))
        for paper in self.catalog.papers:
            section, box = kit.card(pad=24, spacing=24)
            section.setProperty("reading_anchor", True)
            box.addWidget(kit.heading(kit.para(paper.title, "headline"), kit.para(f"발표일 {paper.published_date or '미확인'} · 확인일 {paper.checked_date}", "caption", "secondary")))
            box.addWidget(kit.para(paper.summary))
            box.addWidget(kit.para(paper.beginner_explanation))
            box.addWidget(kit.para("읽기에 필요한 개념 · " + ", ".join(paper.prerequisites), "caption", "secondary"))
            details = SourceDetails(self)
            details.body.addWidget(kit.para(f"검토한 버전 {paper.examined_version or '미확인'}\n{paper.verification_scope}", "caption", "secondary"))
            details.body.addWidget(kit.para(f"논문 이용 조건 · {paper.license_label}\n{paper.license_scope}", "caption", "secondary"))
            button = kit.button("논문 원문 열기", "text")
            button.setVisible(self.on_paper is not None)
            button.clicked.connect(lambda checked=False, item=paper: self.open_paper(item))
            figure = kit.button("그림 설명 보기")
            figure.setVisible(bool(self.on_figure and paper.figure_description))
            figure.clicked.connect(lambda checked=False, item=paper: self.open_figure(item))
            license_button = kit.button("이용 조건 원문", "text")
            license_button.setVisible(bool(self.on_source and paper.license_url))
            license_button.clicked.connect(lambda checked=False, url=paper.license_url: self.on_source(url))
            details.body.addWidget(flow_buttons(license_button))
            box.addWidget(flow_buttons(button, figure))
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
