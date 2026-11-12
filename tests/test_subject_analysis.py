# -*- coding: utf-8 -*-
"""실제 저장 API의 기록을 집계해 과목별 분모·반복·오류·공개 범위를 확인함."""
import contextlib
import datetime
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock
import xml.etree.ElementTree as ET

import adaptive
import session
import study
import subject_analysis as analysis
from aiprep import bank as ai_bank, service as ai_service
from journey import bank as journey_bank, node as journey_node
from journey.service import JourneySession
from webprep import bank as web_bank, record, stack
from webprep.service import WebSession

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = "private-contact@example.invalid"


def tool(name):
    spec = importlib.util.spec_from_file_location("subject_test_" + name, ROOT / "tests" / ("legacy_" + name + ".py") if name in ("dashboard", "ci_report") else ROOT / "tools" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AnalysisTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="subject_analysis_")
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.subs = self.base / "submissions"
        self.journey = self.base / "dungeons"
        shutil.copytree(ROOT / "tests/journey_bank", self.journey)
        index = study.read_json(self.journey / "index.json")
        index["dungeons"] = [row for row in index["dungeons"] if row["id"] in ("t01", "t03")]
        study.write_text(self.journey / "index.json", json.dumps(index))
        self.web = self.base / "web"
        shutil.copytree(ROOT / "tests/web_bank", self.web)
        index = study.read_json(self.web / "index.json")
        index["topics"].append({"id": "t92", "no": 92, "title": "개인 경력"})
        study.write_text(self.web / "index.json", json.dumps(index))
        study.write_text(self.web / "drills/t92/meta.json", json.dumps({"local": True, "chains": [{"id": "90-C", "title": "내 경력"}]}))
        cat = adaptive.catalog()
        self.cat = {key: cat[key] for key in sorted(cat)[:2]}
        self.clock = "2026-11-01T12:00:00"
        for target, name, value in (
            (study, "SUBMISSIONS_DIR", str(self.subs)),
            (journey_bank, "BANK_DIR", str(self.journey)),
            (web_bank, "BANK_DIR", str(self.web)),
            (ai_bank, "AI_DIR", str(ROOT / "tests/ai_bank")),
            (adaptive, "catalog", lambda: self.cat),
            (adaptive, "now", lambda: self.clock),
            (ai_service, "now", lambda: self.clock),
            (analysis, "_calendar_day", lambda: datetime.date(2026, 11, 5)),
        ):
            patcher = mock.patch.object(target, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def collect(self, user="learner"):
        return analysis.collect_user(user)

    def subjects(self, user="learner"):
        return {row.key: row for row in self.collect(user).subjects}

    def metrics(self, subject):
        return {metric.key: (metric.value, metric.total) for metric in self.subjects()[subject].metrics}

    def save_python(self):
        keys = list(self.cat)
        rnd = {"id": "r01", "kind": "round", "items": keys}
        prof = adaptive.load_profile("learner")
        prof.update(rounds=[rnd], contact=PRIVATE)
        wrong = [{"key": keys[0], "state": "wrong", "earned": 0, "points": 1},
                 {"key": keys[1], "state": "blank", "earned": 0, "points": 1}]
        adaptive.record(prof, rnd, wrong, finalize=True)
        adaptive.record(prof, rnd, wrong, finalize=True)
        right = [dict(wrong[0], state="ok", earned=1), wrong[1]]
        adaptive.record(prof, rnd, right, finalize=True)
        rnd["completed_at"] = self.clock
        adaptive.save_profile(prof)

    def save_journey(self):
        sess = JourneySession("learner")
        for item, lang, passed in (("t01/p1", "python", False), ("t01/p1", "python", True),
                                   ("t01/p1", "javascript", True), ("t01/p2", "python", False)):
            sess._append({"kind": "grade", "item": item, "lang": lang, "passed": passed,
                          "score": 100 if passed else 40, "note": PRIVATE})

    def save_web(self, user="learner", local_only=False):
        rec = record.Record(str(self.subs / user / "web/record.json"), user)
        entries = [{"kind": "drill", "chain": "90-C", "q": 1, "note": PRIVATE},
                   {"kind": "chain", "chain": "90-C", "result": "pass"}]
        if not local_only:
            entries += [{"kind": "learn", "page": "l90"}, {"kind": "learn", "page": "l90"},
                        {"kind": "drill", "chain": "90-A", "q": 1, "note": PRIVATE},
                        {"kind": "drill", "chain": "90-A", "q": 2},
                        {"kind": "chain", "chain": "90-A", "result": "pass"},
                        {"kind": "receive", "item": "x01", "try": 1},
                        {"kind": "live", "item": "x01", "try": 1},
                        {"kind": "check", "item": "x01", "try": 1},
                        {"kind": "finish", "item": "x01", "try": 1},
                        {"kind": "receive", "item": "x01", "try": 2}]
        for row in entries:
            rec.append(row, at=self.clock)

    def save_ai(self):
        sess = ai_service.AiSession("learner", home=str(self.base / "local"))
        sess.mark_read("i90", "90a")
        sess.mark_read("i90", "90a")
        sess.save_recall("i90", "90a", "r2", True)
        sess.save_recall("i90", "90a", "v1", False, level=7)
        sess.save_revisit("i90", "90a")
        other = next(cid for cid, card in sess.cards.items() if card["kind"] == "stmt")
        entries = [
            {"kind": "answer", "set": "one", "card": "i90-b01", "again": 0, "result": "stuck", "value": [PRIVATE], "also": {other: "pass"}},
            {"kind": "override", "set": "one", "card": "i90-b01", "again": 0},
            {"kind": "answer", "set": "one", "card": "i90-b01", "again": 1, "result": "pass"},
            {"kind": "answer", "set": "one", "card": "i90-b02", "again": 0, "result": "stuck"},
        ]
        for row in entries:
            sess.record.append(row, at=self.clock)
        self.clock = "2026-11-05T12:00:00"

    def test_missing_submission_does_not_infer_learning_has_not_started(self):
        result = self.collect()
        self.assertEqual([key for key, _ in analysis.SUBJECTS], [s.key for s in result.subjects])
        self.assertEqual(["no_record"] * 4, [s.status for s in result.subjects])
        self.assertTrue(all(s.source == "submitted" and not s.metrics for s in result.subjects))
        self.assertFalse(self.subs.exists())
        text = analysis.markdown([result])
        self.assertIn("제출 기록 없음", text)
        self.assertNotIn("시작 전", text)
        self.assertNotIn("진단 테스트를 시작", text)

    def test_python_skips_and_unchanged_regrades_do_not_inflate_answers(self):
        self.save_python()
        values = self.metrics("python")
        self.assertEqual((1, 2), values["answered_items"])
        self.assertEqual((2, None), values["answers"])
        self.assertEqual((1, None), values["repeats"])
        self.assertEqual((1, 1), values["finished_rounds"])

    def test_journey_counts_languages_once_and_respects_boss_lock(self):
        self.save_journey()
        values = self.metrics("journey")
        self.assertEqual((2, 4), values["tried_items"])
        self.assertEqual((1, 4), values["passed_items"])
        self.assertEqual((4, None), values["grades"])
        self.assertEqual((2, None), values["repeats"])
        self.assertEqual("t01/p2", self.subjects()["journey"].next_action.target)

    def test_web_uses_last_mission_try_and_omits_local_chains(self):
        self.save_web()
        values = self.metrics("web")
        self.assertEqual((1, 1), values["opened_notes"])
        self.assertEqual((0, 1), values["finished_missions"])
        self.assertEqual((1, 3), values["tried_chains"])
        self.assertEqual((1, None), values["checks"])
        self.assertEqual((2, None), values["answers"])
        self.assertEqual((1, None), values["due"])
        self.assertEqual("x01", self.subjects()["web"].next_action.target)

    def test_local_web_entries_do_not_become_public_activity(self):
        self.save_web(local_only=True)
        self.assertEqual("no_record", self.subjects()["web"].status)
        self.assertEqual({}, self.metrics("web"))

    def local_web_overview(self):
        home = self.base / "private-web"
        local = record.Record(str(home / "record.json"), "learner")
        local.append({"kind": "drill", "chain": "90-C", "q": 1, "note": PRIVATE}, at=self.clock)
        local.append({"kind": "chain", "chain": "90-C", "result": "pass"}, at=self.clock)
        sess = WebSession("learner", home=str(home))
        with mock.patch.object(sess, "stack_state", return_value={}):
            return sess.overview(), home

    def test_private_web_home_is_not_a_submission_source(self):
        view, home = self.local_web_overview()
        before = {str(p): p.read_bytes() for p in home.rglob("*") if p.is_file()}
        with mock.patch.dict(os.environ, {"STUDY_WEB_HOME": str(home)}), \
                mock.patch.object(stack, "home_dir", side_effect=AssertionError("unexpected home lookup")), \
                mock.patch.object(study, "read_json", side_effect=AssertionError("unexpected local read")):
            submitted = self.subjects()["web"]
        self.assertEqual("no_record", submitted.status)
        self.assertEqual("submitted", submitted.source)
        self.assertEqual((), submitted.metrics)
        self.assertFalse(self.subs.exists())

        with mock.patch.object(study, "read_json", side_effect=AssertionError("unexpected overview read")), \
                mock.patch.object(study, "write_text", side_effect=AssertionError("unexpected overview write")):
            local = analysis.from_overviews("learner", {"web": view})
        web = local.subjects[2]
        values = {m.key: (m.value, m.total) for m in web.metrics}
        self.assertEqual((1, 3), values["topic_chains"])
        self.assertEqual((1, None), values["activity_days"])
        self.assertEqual(("available", "service"), (web.status, web.source))
        self.assertEqual(before, {str(p): p.read_bytes() for p in home.rglob("*") if p.is_file()})
        output = analysis.markdown([local])
        self.assertIn("이 기기 서비스", output)
        self.assertIn("서비스 확인", output)
        self.assertNotIn("제출 기록 있음", output)
        for private in (PRIVATE, str(home)):
            self.assertNotIn(private, json.dumps(local.to_dict(), ensure_ascii=False))

    def test_record_link_cannot_turn_external_web_home_into_submitted_data(self):
        _, home = self.local_web_overview()
        submitted = self.subs / "learner/web/record.json"
        submitted.parent.mkdir(parents=True)
        try:
            submitted.symlink_to(home / "record.json")
        except OSError:
            self.skipTest("이 환경에서 기록 파일의 심볼릭 링크를 만들 수 없습니다.")
        with mock.patch.object(study, "read_json", side_effect=AssertionError("unexpected external read")):
            web = self.subjects()["web"]
        self.assertEqual(("unavailable", "source"), (web.status, web.issue))
        self.assertFalse(web.metrics)

    def test_all_four_real_service_overviews_keep_their_own_count_definitions(self):
        self.save_python(); self.save_journey(); self.save_web(); self.save_ai()
        web = WebSession("learner", home=str(self.base / "local-web"))
        with mock.patch.object(web, "stack_state", return_value={}):
            overviews = {"python": session.Session("learner").overview(),
                         "journey": JourneySession("learner").overview(),
                         "web": web.overview(),
                         "ai": ai_service.AiSession("learner", home=str(self.base / "local-ai")).overview()}
        result = analysis.from_overviews("learner", overviews)
        self.assertEqual(["available"] * 4, [s.status for s in result.subjects])
        values = {s.key: {m.key: (m.value, m.total) for m in s.metrics} for s in result.subjects}
        self.assertEqual((2, None), values["python"]["first_grades"])
        self.assertEqual((1, 4), values["journey"]["passed_items"])
        self.assertEqual((2, 3), values["web"]["topic_chains"])
        self.assertEqual((1, 2), values["ai"]["read_units"])
        public = analysis.markdown([result])
        for private in (PRIVATE, "readiness", "준비도", "숙달"):
            self.assertNotIn(private, public)
        self.assertNotIn("제출된 파일만 집계", public)

    def test_service_zero_is_observed_but_missing_overview_is_unknown(self):
        sess = WebSession("learner", home=str(self.base / "empty-home"))
        with mock.patch.object(sess, "stack_state", return_value={}):
            view = sess.overview()
        row = analysis.from_overviews("learner", {"web": view})
        self.assertEqual(["unavailable", "unavailable", "available", "unavailable"], [s.status for s in row.subjects])
        self.assertTrue(all(s.source == "service" for s in row.subjects))
        self.assertTrue(all(m.value == 0 for m in row.subjects[2].metrics))
        self.assertTrue(all(not s.metrics for s in row.subjects if s.status == "unavailable"))
        self.assertEqual("no_record", self.subjects()["web"].status)

    def test_invalid_service_overview_is_unknown_without_leaking_error_details(self):
        view, _ = self.local_web_overview()
        for broken in (None, {}, dict(view, bank_errors=[PRIVATE]), dict(view, done_missions=-1)):
            with self.subTest(value=broken):
                result = analysis.from_overviews("learner", {"web": broken})
                self.assertEqual("unavailable", result.subjects[2].status)
                self.assertFalse(result.subjects[2].metrics)
                self.assertNotIn(PRIVATE, analysis.markdown([result]))

    def test_ai_has_separate_unit_recall_response_and_schedule_counts(self):
        self.save_ai()
        values = self.metrics("ai")
        self.assertEqual((1, 2), values["read_units"])
        self.assertEqual((3, 17), values["answered_items"])
        self.assertEqual((3, None), values["answers"])
        self.assertEqual((1, None), values["repeats"])
        self.assertEqual((2, None), values["recalls"])
        self.assertEqual((1, None), values["revisits"])
        self.assertEqual((3, None), values["due"])

    def test_corrupt_record_is_unknown_and_does_not_hide_other_subjects(self):
        self.save_web()
        study.write_text(self.subs / "learner/journey/progress.json", "{" + PRIVATE)
        subjects = self.subjects()
        self.assertEqual("unavailable", subjects["journey"].status)
        self.assertEqual((), subjects["journey"].metrics)
        self.assertEqual("available", subjects["web"].status)
        self.assertEqual("no_record", subjects["python"].status)
        self.assertNotIn(PRIVATE, analysis.markdown([self.collect()]))

    def test_record_path_as_a_directory_is_not_an_empty_history(self):
        (self.subs / "learner/ai/record.json").mkdir(parents=True)
        self.assertEqual("unavailable", self.subjects()["ai"].status)

    def test_catalog_failure_has_no_invented_zero_denominator(self):
        self.save_python()
        with mock.patch.object(adaptive, "catalog", side_effect=ValueError(PRIVATE)):
            subjects = self.subjects()
        self.assertEqual("unavailable", subjects["python"].status)
        self.assertEqual((), subjects["python"].metrics)
        self.assertEqual(["no_record"] * 3, [subjects[key].status for key in ("journey", "web", "ai")])

    def test_collect_is_read_only_and_does_not_probe_node_or_grade_code(self):
        self.save_python(); self.save_journey(); self.save_web(); self.save_ai()
        before = {str(p): p.read_bytes() for p in self.subs.rglob("*") if p.is_file()}
        with mock.patch.object(study, "write_text", side_effect=AssertionError("unexpected write")), \
                mock.patch.object(study, "grade_user", side_effect=AssertionError("unexpected grade")), \
                mock.patch.object(journey_node, "find", side_effect=AssertionError("unexpected Node probe")), \
                mock.patch.object(stack, "find_node", side_effect=AssertionError("unexpected Node probe")):
            result = self.collect()
        self.assertEqual(["available"] * 4, [s.status for s in result.subjects])
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.subs.rglob("*") if p.is_file()})
        self.assertNotIn(PRIVATE, json.dumps(result.to_dict(), ensure_ascii=False))

    def test_team_includes_members_without_python_profiles(self):
        self.save_web("web-only")
        self.save_journey()
        rows = analysis.collect_team().users
        self.assertEqual(["learner", "web-only"], [row.user for row in rows])
        self.assertEqual("available", rows[1].subjects[2].status)

    def test_team_storage_error_is_not_reported_as_no_submissions(self):
        self.subs.write_text("not a directory")
        team = analysis.collect_team()
        self.assertEqual("unavailable", team.status)
        report, _ = adaptive.team_analysis_markdown(self.cat)
        self.assertEqual(4, report.count("| 학습자 목록 |"))
        self.assertNotIn("시작 전", report)

    def test_invalid_identifier_cannot_read_outside_submissions(self):
        with self.assertRaises(ValueError):
            self.collect("../outside")

    def test_markdown_and_dashboard_share_the_four_subjects_without_readiness(self):
        self.save_python(); self.save_journey(); self.save_web(); self.save_ai()
        rows = analysis.collect_team().users
        dashboard = tool("dashboard")
        md, svg = dashboard.render_markdown(rows), dashboard.render_svg(rows)
        for output in (md, svg, adaptive.user_analysis_markdown("learner", self.cat)):
            for _, title in analysis.SUBJECTS:
                self.assertIn(title, output)
            for private in (PRIVATE, "준비도", "숙달", "readiness"):
                self.assertNotIn(private, output)
        self.assertIn("답한 문항 1/2개", md)
        tree = ET.fromstring(svg)
        groups = tree.findall("{http://www.w3.org/2000/svg}g")
        self.assertEqual([key for key, _ in analysis.SUBJECTS], [g.attrib["data-subject"] for g in groups])

    def test_ci_comment_contains_all_subjects_when_only_web_changed(self):
        self.save_web()
        ci = tool("ci_report")
        env = {"GITHUB_BASE_REF": "main", "GITHUB_STEP_SUMMARY": ""}
        with mock.patch.object(study, "ROOT", str(self.base)), \
                mock.patch.object(ci, "changed_files", return_value=["submissions/learner/web/record.json"]), \
                mock.patch.dict(os.environ, env), contextlib.redirect_stdout(io.StringIO()):
            ci.main()
        report = study.read_text(self.base / "report.md")
        for _, title in analysis.SUBJECTS:
            self.assertIn(title, report)
        self.assertIn("열어 본 노트 1/1개", report)
        self.assertNotIn(PRIVATE, report)

    def test_ci_comment_uses_every_submitted_subject_when_only_one_changed(self):
        self.save_python(); self.save_journey(); self.save_web(); self.save_ai()
        ci = tool("ci_report")
        env = {"GITHUB_BASE_REF": "main", "GITHUB_STEP_SUMMARY": ""}
        with mock.patch.object(study, "ROOT", str(self.base)), \
                mock.patch.object(ci, "changed_files", return_value=["submissions/learner/ai/record.json"]), \
                mock.patch.dict(os.environ, env), contextlib.redirect_stdout(io.StringIO()):
            ci.main()
        report = study.read_text(self.base / "report.md")
        for text in ("답한 문항 1/2개", "통과한 문제 1/4개", "열어 본 노트 1/1개", "끝까지 연 단원 1/2개"):
            self.assertIn(text, report)
        self.assertNotIn(PRIVATE, report)

    def test_legacy_grade_failure_preserves_other_subjects_without_error_details(self):
        self.save_web()
        ci = tool("ci_report")
        item = next(iter(self.cat.values()))
        (self.subs / "learner" / item["unit"]).mkdir()
        env = {"GITHUB_BASE_REF": "main", "GITHUB_STEP_SUMMARY": ""}
        with mock.patch.object(study, "ROOT", str(self.base)), \
                mock.patch.object(study, "grade_user", side_effect=ValueError(PRIVATE)), \
                mock.patch.object(ci, "changed_files", return_value=["submissions/learner/web/record.json"]), \
                mock.patch.dict(os.environ, env), contextlib.redirect_stdout(io.StringIO()):
            ci.main()
        report = study.read_text(self.base / "report.md")
        self.assertIn("기존 세트 채점은 확인 불가", report)
        self.assertIn("열어 본 노트 1/1개", report)
        for _, title in analysis.SUBJECTS:
            self.assertIn(title, report)
        self.assertNotIn(PRIVATE, report)

    def test_legacy_grade_keeps_scores_without_printing_private_failure_details(self):
        ci = tool("ci_report")
        item = next(iter(self.cat.values()))
        (self.subs / "learner" / item["unit"]).mkdir(parents=True)
        graded = [(item["set"], [{"id": "Q1", "state": "wrong", "earned": 0, "points": 1, "detail": PRIVATE}])]
        env = {"GITHUB_BASE_REF": "main", "GITHUB_STEP_SUMMARY": ""}
        with mock.patch.object(study, "ROOT", str(self.base)), \
                mock.patch.object(study, "grade_user", return_value=graded) as grade, \
                mock.patch.object(ci, "changed_files", return_value=["submissions/learner/" + item["unit"] + "/quiz.py"]), \
                mock.patch.dict(os.environ, env), contextlib.redirect_stdout(io.StringIO()):
            ci.main()
        grade.assert_called_once_with("learner")
        report = study.read_text(self.base / "report.md")
        self.assertIn("0/1", report)
        self.assertIn("미통과", report)
        self.assertNotIn(PRIVATE, report)
        self.assertNotIn(chr(0x2014), report)


if __name__ == "__main__":
    unittest.main()
