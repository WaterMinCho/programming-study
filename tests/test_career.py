"""공개 자료의 식별자·날짜·오프라인 읽기와 기존 목표 연결을 확인함."""
from dataclasses import replace
from datetime import datetime
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from career.catalog import DATA, GOAL_IDS, load_catalog, sort_videos
from learning_data.goals import catalog as goal_catalog

ROOT = Path(__file__).resolve().parents[1]


class CareerCatalogTest(unittest.TestCase):
    def setUp(self):
        self.catalog = load_catalog()

    def test_offline_catalog_preserves_six_goals_and_current_revision(self):
        with patch("socket.socket", side_effect=AssertionError("네트워크 사용")):
            catalog = load_catalog()
        self.assertEqual(catalog.states, {"roles": "ready", "videos": "ready", "papers": "ready"})
        self.assertEqual(tuple(goal["goal_id"] for goal in catalog.goals), GOAL_IDS)
        self.assertEqual(catalog.roadmap_revision, goal_catalog(ROOT)["roadmap_revision"])
        self.assertEqual(len(catalog.roles), 11)

    def test_all_role_node_links_exist_in_canonical_roadmap(self):
        canonical = json.loads((ROOT / "tools/roadmap/roadmap.json").read_text())
        # 원본을 고치지 않고 기존 노드의 연결만 확인함.
        def nodes(value):
            if isinstance(value, dict):
                yield value
                for child in value.values():
                    yield from nodes(child)
            elif isinstance(value, list):
                for child in value:
                    yield from nodes(child)
        by_goal = {path["id"]: {node.get("id") for node in nodes(path)} for path in canonical["paths"]}
        for role in self.catalog.roles:
            for node in role["roadmap_nodes"]:
                self.assertIn(node["node_id"], by_goal[node["goal_id"]])

    def test_browsing_filters_do_not_change_goal_relation(self):
        roles = self.catalog.roles_for("digital_services", "web_service")
        self.assertEqual({role["id"] for role in roles}, {"frontend", "backend", "qa"})
        self.assertEqual(self.catalog.role("frontend")["goal_links"][0]["relation"], "shared_skills_only")
        self.assertIsNone(self.catalog.role("unknown"))
        self.assertEqual(self.catalog.roles_for("unknown"), ())

    def test_video_ids_counts_and_newest_upload_first(self):
        videos = self.catalog.videos
        self.assertEqual(sum(video.origin == "selected" for video in videos), 18)
        self.assertEqual(sum(video.origin == "additional" for video in videos), 20)
        self.assertEqual(len({video.video_id for video in videos}), 38)
        actual = [datetime.fromisoformat(video.uploaded_at_utc.replace("Z", "+00:00")) for video in videos]
        self.assertEqual(actual, sorted(actual, reverse=True))

    def test_unknown_dates_ties_and_date_only_do_not_invent_times(self):
        video = self.catalog.videos[0]
        unknown = replace(video, video_id="unknown____", upload_date=None, uploaded_at_utc=None)
        first = replace(video, video_id="aaaaaaaaaaa", uploaded_at_utc=None)
        second = replace(first, video_id="bbbbbbbbbbb")
        self.assertEqual(sort_videos([unknown, second, first]), (first, second, unknown))
        self.assertIsNone(first.uploaded_at_utc)
        self.assertEqual(unknown.date_label, "업로드 날짜 미확인")
        self.assertEqual(replace(video, duration_seconds=None).duration_label, "길이 미확인")
        self.assertEqual(replace(video, duration_seconds=3601).duration_label, "1:00:01")

    def test_missing_empty_broken_and_other_catalogs_are_independent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(set(load_catalog(root).states.values()), {"unavailable"})
            (root / "videos.json").write_text('{"schema_version": 1, "videos": []}')
            self.assertEqual(load_catalog(root).states["videos"], "empty")
            (root / "videos.json").write_text("{")
            self.assertEqual(load_catalog(root).states["videos"], "invalid")
            (root / "videos.json").write_bytes((DATA / "videos.json").read_bytes())
            (root / "roles.json").write_text("[]")
            catalog = load_catalog(root)
            self.assertEqual(catalog.states["roles"], "invalid")
            self.assertEqual(len(catalog.videos), 38)

    def test_bad_video_data_closes_only_video_catalog(self):
        raw = json.loads((DATA / "videos.json").read_text())
        mutations = [lambda row: row.update(video_id="../wrong"), lambda row: row.update(url="https://example.org"),
                     lambda row: row.update(upload_date="2026-02-30"), lambda row: row.update(uploaded_at_utc="2026-01-01T00:00:00"),
                     lambda row: row.update(duration_seconds=-1), lambda row: row.update(embeddable="yes")]
        for mutate in mutations:
            with self.subTest(mutate=mutate), tempfile.TemporaryDirectory() as directory:
                payload = json.loads(json.dumps(raw))
                mutate(payload["videos"][0])
                (Path(directory) / "videos.json").write_text(json.dumps(payload))
                self.assertEqual(load_catalog(directory).states["videos"], "invalid")

    def test_duplicate_videos_and_bad_goal_links_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = json.loads((DATA / "videos.json").read_text())
            raw["videos"].append(raw["videos"][0])
            (root / "videos.json").write_text(json.dumps(raw))
            self.assertEqual(load_catalog(root).states["videos"], "invalid")
            raw = json.loads((DATA / "roles.json").read_text())
            raw["roles"][0]["goal_links"][0]["goal_id"] = "new_goal"
            (root / "roles.json").write_text(json.dumps(raw))
            self.assertEqual(load_catalog(root).states["roles"], "invalid")

    def test_paper_schema_accepts_supplied_content_and_keeps_scope_and_rights(self):
        self.assertEqual(len(self.catalog.papers), 5)
        for paper in self.catalog.papers:
            self.assertTrue(paper.license_url.startswith("https://arxiv.org/"))
            self.assertEqual(len(paper.figure_description), 4)
            self.assertTrue(paper.prerequisites)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "papers.json").write_text(json.dumps({"schema_version": 1, "papers": [{
                "paper_id": "fixture", "title": "임시 논문", "url": "https://example.org/paper", "published_date": None,
                "summary": "검사용 임시 자료의 요약을 표시합니다.", "beginner_explanation": "검사용으로 넣은 짧은 설명을 표시합니다.", "checked_date": "2026-11-14"}]}))
            catalog = load_catalog(root)
            self.assertEqual(catalog.states["papers"], "ready")
            self.assertEqual(catalog.papers[0].paper_id, "fixture")

    def test_required_videos_keep_transcript_and_visual_review_separate(self):
        for video_id in ("H89Az-iZZrc", "HCx2ICUe0eA"):
            video = next(video for video in self.catalog.videos if video.video_id == video_id)
            self.assertEqual(video.transcript_review, "full_transcript_reviewed")
            self.assertEqual(video.visual_review, "selected_scenes_reviewed")
            self.assertIn("전체 영상 시청", video.limitations)
            self.assertEqual(video.review_label, "전체 대본 검토 완료")

    def test_public_data_contains_no_internal_material_or_local_paths(self):
        for path in DATA.glob("*.json"):
            text = path.read_text()
            for private in ("/Users/", "transcript_segments", "chapter_matrix", "evidence_file", "session_token", "local_path"):
                self.assertNotIn(private, text, str(path))


if __name__ == "__main__":
    unittest.main()
