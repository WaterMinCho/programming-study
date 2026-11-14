"""커리어 화면을 필요할 때 만들고 학습 저장·영상 종료 흐름에 연결함."""
import json
from datetime import datetime, timezone

from PyQt6.QtCore import QTimer

from gui import motion
from gui.worker import Job


class CareerController:
    def __init__(self, win):
        self.win = win
        self.catalog = self.roadmap = self.magazine = None
        self.video = self.paper = self.setup_job = None

    def _catalog(self):
        if self.catalog is None:
            from career import load_catalog
            self.catalog = load_catalog()
        return self.catalog

    def _attach(self, page):
        self.win.pages.addWidget(page)
        self.win.workspace.overview_pages += (page,)
        return page

    def show_roadmap(self):
        if not self.win.leave_pages(self.show_roadmap, "저장하지 않고 나가기"):
            return
        if self.roadmap is None:
            from gui.career_roadmap import CareerRoadmapPage
            self.roadmap = self._attach(CareerRoadmapPage(
                catalog=self._catalog(), on_back=self.win.go_hub,
                on_select_goal=self.select_role, on_magazine=lambda: self.show_magazine(),
                on_video=self.show_magazine, on_source=self.win.open_url))
            try:
                saved = json.loads(self.win.settings.value("career/role/" + self.win.user, "{}"))
            except (ValueError, TypeError):
                saved = {}
            if isinstance(saved, dict) and self.roadmap.select_role(saved.get("role_id")):
                self.roadmap.set_saved_role(saved["role_id"])
                self.roadmap.show_catalog()
        self.win.area = "career_roadmap"
        motion.switch(self.win.pages, self.roadmap)

    def show_magazine(self, video_id=None):
        if not self.win.leave_pages(lambda: self.show_magazine(video_id), "저장하지 않고 나가기"):
            return
        if self.magazine is None:
            from gui.career_magazine import CareerMagazinePage
            self.magazine = self._attach(CareerMagazinePage(
                catalog=self._catalog(), on_back=self.show_roadmap,
                on_video=self.play_video, on_stop=self.stop_video,
                on_source=self.win.open_url, on_paper=lambda paper: self.win.open_url(paper.url),
                on_figure=self.explain_paper))
        self.win.area = "career_magazine"
        motion.switch(self.win.pages, self.magazine)
        if video_id is not None:
            self.magazine._change_tab(0)
            self.magazine.select_video(video_id, reveal=True)

    def select_role(self, role_id, coarse_goal_id):
        role = self._catalog().role(role_id)
        if role is None:
            return
        selected = {"role_id": role_id, "catalog_version": self.catalog.version,
                    "selected_at": datetime.now(timezone.utc).isoformat()}
        self.win.settings.setValue("career/role/" + self.win.user, json.dumps(selected, ensure_ascii=False))
        self.roadmap.set_saved_role(role_id)

    def play_video(self, video):
        from gui.video_viewer import VideoDialog
        self.stop_video()
        self.video = dialog = VideoDialog(self.win, video, self.win.open_url, on_prepare=self.prepare_video)
        def changed(state):
            if self.video is not dialog or self.magazine.selected_video_id != video.video_id:
                return
            if state == "playing":
                self.magazine._requested_id = video.video_id
            self.magazine.set_playback_state(video.video_id, state, dialog.status.text() if state == "error" else "")

        dialog.state_changed.connect(changed)
        dialog.finished.connect(lambda *_: self._video_closed(dialog))
        dialog.open()

    def _video_closed(self, dialog):
        if self.video is dialog:
            self.video = None
            self.magazine.stop_playback()
            dialog.deleteLater()

    def stop_video(self):
        dialog, self.video = self.video, None
        if dialog is not None:
            dialog.close()
            dialog.deleteLater()

    def prepare_video(self, done):
        from tools.video_setup import install
        if self.setup_job is not None:
            done({"ok": False, "message": "앱 내 재생기를 설치하고 있습니다."})
            return None
        job = self.setup_job = Job(lambda: install(job.cancel))
        owner = self.video

        def finish(result):
            if owner is self.video and owner is not None:
                accepted = done(result)
                if accepted and result.get("ok") and result.get("restart"):
                    self.stop_video()
                    self.win._restart({"message": "앱 내 재생기를 설치했습니다. 프로그램을 다시 시작해 주세요."})

        def stopped():
            self.setup_job = None
            job.deleteLater()
            if self.win.close_pending:
                QTimer.singleShot(0, self.win.close)

        job.done.connect(finish)
        job.failed.connect(lambda *_: finish({"ok": False, "message": "앱 내 재생기를 설치하지 못했습니다."}))
        job.finished.connect(stopped)
        job.start()
        return job.cancel.set

    def explain_paper(self, paper):
        from gui.paper_explainer import PaperExplanationDialog
        self.paper = dialog = PaperExplanationDialog(paper, self.win)

        def closed(*_):
            if self.paper is dialog:
                self.paper = None
            dialog.deleteLater()

        dialog.finished.connect(closed)
        dialog.open()

    def stop(self):
        self.stop_video()
        if self.paper is not None:
            self.paper.close()
        if self.setup_job is not None:
            self.setup_job.cancel.set()
            return False
        return True
