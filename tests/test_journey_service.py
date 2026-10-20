# -*- coding: utf-8 -*-
"""여정 은행·채점·서비스 테스트. 고정 은행 tests/journey_bank(던전 t01 에 기초·중급·선택·보스 하나씩, 일부러 깨진 t02,
준비 중 t03~t16)으로 진행 기록, 잠금 규칙, 힌트·해설, 코드·케이스 저장, 실제 하네스로 돌리는 실행·채점을 봄.

실행: python -m unittest tests.test_journey_service
시간 값(ms)은 단언하지 않고 판정만 봄. STUDY_LEAN_CI 가 있으면 모두 건너뛰고, Node 가 없으면 JS 테스트를 건너뜀.
"""
import os

os.environ.setdefault("STUDY_NODE_PROBE", "0")

import datetime  # noqa: E402
import json  # noqa: E402
import shutil  # noqa: E402
import sys  # noqa: E402
import tempfile  # noqa: E402
import threading  # noqa: E402
import unittest  # noqa: E402
from unittest import mock  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import adaptive  # noqa: E402
import session  # noqa: E402
import study  # noqa: E402
from journey import bank, grading, node, runner, values  # noqa: E402
from journey.service import JourneyError, JourneySession  # noqa: E402

LEAN = bool(os.environ.get("STUDY_LEAN_CI"))
NODE = None if LEAN else node.find()
FIXTURE = os.path.join(ROOT, "tests", "journey_bank")
SKIP_LEAN = unittest.skipIf(LEAN, "자식 프로세스를 띄우는 테스트는 journey.yml 에서 돎")

# 커리큘럼 2절 표: (id, 제목, 주제, 보스 목표, 권장 선행)
CURRICULUM = [
    ("d01", "향신료 시장", "해시·투 포인터", "G3 / Lv3", []),
    ("d02", "용암 평원", "누적합·차분", "G2 / Lv3", ["d01"]),
    ("d03", "모래시계 탑", "이분 탐색", "G3 / Lv3~4", ["d01"]),
    ("d04", "태엽 공방", "구현·시뮬레이션", "G2 / Lv3", ["d01", "d02"]),
    ("d05", "얼음 미궁", "BFS 심화", "G2 / Lv3 상", []),
    ("d06", "메아리 동굴", "스택·큐·덱", "G1 / Lv3~4", ["d02"]),
    ("d07", "봉인 사원", "완전 탐색·백트래킹", "G2 / Lv3", ["d05"]),
    ("d08", "용병 길드", "힙·그리디", "G1 / Lv3~4", ["d01", "d04"]),
    ("d09", "기억의 도서관", "DP Ⅰ", "G2 / Lv4", ["d01"]),
    ("d10", "별빛 항로", "최단 경로", "G1~P5 / Lv4", ["d05", "d06", "d08"]),
    ("d11", "연결과 순서의 다리", "유니온 파인드·위상 정렬", "G1 / Lv4", ["d08", "d09"]),
    ("d12", "룬 공방", "DP Ⅱ 구간 DP", "G1 / Lv4", ["d09"]),
    ("d13", "차원의 서고", "비트마스크 DP", "G1~P5 / Lv4", ["d07", "d09"]),
    ("d14", "세계수", "트리 DP", "P5 / Lv4", ["d09", "d11"]),
    ("d15", "속삭이는 사전", "트라이·문자열", "G1~P5 / Lv4", ["d01", "d07", "d14"]),
    ("d16", "시간의 탑", "펜윅·세그먼트·오프라인", "P5~P4 / Lv4", ["d03", "d08"]),
]

SYNTAX_ERROR = "def solution(nums):\n    return (\n"
# 최상위 코드가 한 번 돈 다음 프로세스부터 실패함. 케이스 폴더의 위(..)가 실행·채점 한 번의 임시 폴더임
FAILS_AFTER_FIRST = ("import os\n"
                     "if os.path.exists(os.path.join('..', 'flag')):\n"
                     "    raise ValueError('두 번째 프로세스')\n"
                     "open(os.path.join('..', 'flag'), 'w').close()\n\n\n"
                     "def solution(nums):\n"
                     "    return sum(nums)\n")


def read_fixture(rel):
    return study.read_text(os.path.join(FIXTURE, "t01", *rel.split("/")))


def entry(kind, item, **fields):
    record = {"at": adaptive.now(), "kind": kind, "item": item}
    record.update(fields)
    return record


def grade_entry(item, lang="python", passed=True, score=None):
    score = 100.0 if passed else (40.0 if score is None else score)
    return entry("grade", item, lang=lang, score=score, acc=score, eff=0.0, passed=passed, tests=[1, 1, 0, 0])


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="journey_service_")
        self.addCleanup(self.tmp.cleanup)
        for target, name, value in ((study, "SUBMISSIONS_DIR", os.path.join(self.tmp.name, "submissions")),
                                    (runner, "CACHE_DIR", os.path.join(self.tmp.name, "cache")),
                                    (bank, "BANK_DIR", FIXTURE)):
            patcher = mock.patch.object(target, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def progress_path(self, user="alice"):
        return os.path.join(study.SUBMISSIONS_DIR, user, "journey", "progress.json")

    def write_log(self, entries, user="alice"):
        data = {"format": 1, "user": user, "created": adaptive.now(), "log": entries}
        study.write_text(self.progress_path(user), json.dumps(data, ensure_ascii=False, indent=1) + "\n")

    def read_log(self, user="alice"):
        if not os.path.isfile(self.progress_path(user)):
            return []
        return study.read_json(self.progress_path(user))["log"]

    def session(self, user="alice"):
        return JourneySession(user)

    def copy_bank(self):
        """고정 은행의 사본. 봉인 파일을 더하거나 평문을 지우는 테스트가 씀."""
        path = os.path.join(self.tmp.name, "bank")
        shutil.copytree(FIXTURE, path)
        return path


@SKIP_LEAN
class IndexTest(unittest.TestCase):
    def test_index_matches_the_curriculum_table(self):
        entries = bank.read_index(os.path.join(ROOT, "dungeons"))
        self.assertEqual([(e["id"], e["title"], e["topic"], e["boss_target"], e["prereq"]) for e in entries], CURRICULUM)
        self.assertEqual(list(range(1, 17)), [e["no"] for e in entries])
        self.assertEqual(["d16"], [e["id"] for e in entries if e["final"]])

    def test_fixture_index_has_sixteen_dungeons(self):
        entries = bank.read_index(FIXTURE)
        self.assertEqual(16, len(entries))
        self.assertEqual("t01", entries[0]["id"])
        self.assertTrue(entries[-1]["final"])


@SKIP_LEAN
class BankTest(Base):
    def test_load_dungeon_reads_meta_and_problems_in_order(self):
        dungeon = bank.load_dungeon(bank.read_index(FIXTURE)[0], FIXTURE)
        self.assertEqual(["p1", "p2", "p3", "boss"], [p["id"] for p in dungeon["problems"]])
        self.assertEqual(["basic", "mid", "side", "boss"], [p["role"] for p in dungeon["problems"]])
        self.assertEqual(["배열 합", "최댓값 찾기", "문자열 뒤집기"], dungeon["skills"])
        p2 = dungeon["problems"][1]
        self.assertEqual({"accuracy": 80.0, "efficiency": 20.0}, p2["score"])
        self.assertEqual(["p1"], p2["prep"])
        self.assertIsNone(dungeon["problems"][0]["score"])
        self.assertIn("## 문제 설명", p2["markdown"])
        self.assertEqual(["p1", "p2"], dungeon["problems"][-1]["uses"])

    def test_broken_problem_file_raises_bank_error(self):
        with self.assertRaises(bank.BankError) as caught:
            bank.load_dungeon(bank.read_index(FIXTURE)[1], FIXTURE)
        self.assertIn("p1/problem.json 을 읽을 수 없습니다", str(caught.exception))

    def test_plain_secret_paths_cover_wrong_folder_and_dungeon_review(self):
        path = self.copy_bank()
        ddir = os.path.join(path, "t01")
        study.write_text(os.path.join(ddir, "review.json"), "{}\n")
        study.write_text(os.path.join(ddir, "p1", "wrong", "notes.txt"), "보지 않는 파일\n")
        rels = bank.plain_secret_paths(ddir)
        self.assertIn("review.json", rels)
        self.assertIn("p1/wrong/first_only.js", rels)
        self.assertIn("boss/extra.json", rels)
        self.assertNotIn("p1/problem.json", rels)
        self.assertNotIn("p1/wrong/notes.txt", rels)

    def test_plain_file_beats_sealed_and_sealed_is_used_without_plain(self):
        path = self.copy_bank()
        ddir = os.path.join(path, "t01")
        sealed = {"p1/hints.md": "## 1\n\n봉인된 힌트입니다.\n", "p1/only_sealed.md": "봉인에만 있습니다.\n"}
        study.write_text(os.path.join(ddir, "sealed.json"), json.dumps({"note": "봉인", "blob": study.seal_blob(sealed)}))
        files = bank.load_secrets(ddir)
        self.assertEqual(read_fixture("p1/hints.md"), files["p1/hints.md"])
        self.assertEqual("봉인에만 있습니다.\n", files["p1/only_sealed.md"])
        with mock.patch.object(bank, "BANK_DIR", path):
            self.assertIn("한 변수에 모아", self.session().reveal_hint("t01", "p1")["text"])
        os.remove(os.path.join(ddir, "p1", "hints.md"))
        self.assertEqual("## 1\n\n봉인된 힌트입니다.\n", bank.load_secrets(ddir)["p1/hints.md"])
        with mock.patch.object(bank, "BANK_DIR", path):
            self.assertEqual("봉인된 힌트입니다.\n", self.session("bob").reveal_hint("t01", "p1")["text"])

    def test_broken_sealed_file_is_a_journey_error_only_when_secrets_are_needed(self):
        path = self.copy_bank()
        study.write_text(os.path.join(path, "t01", "sealed.json"), '{"note": "봉인", "blob": "not-a-blob"}')
        with self.assertRaises(bank.BankError):
            bank.load_secrets(os.path.join(path, "t01"))
        with mock.patch.object(bank, "BANK_DIR", path):
            journey = self.session()
            self.assertTrue(journey.overview()["dungeons"][0]["ready"])
            with self.assertRaises(JourneyError):
                journey.problem("t01", "p1", "python")

    def test_parse_hints_splits_numbered_sections(self):
        self.assertEqual(["첫 힌트\n", "둘째 힌트 첫 줄\n\n둘째 힌트 셋째 줄\n"],
                         bank.parse_hints("머리말\n## 1\n첫 힌트\n\n## 2\n둘째 힌트 첫 줄\n\n둘째 힌트 셋째 줄\n"))
        self.assertEqual([], bank.parse_hints(None))


@SKIP_LEAN
class OverviewTest(Base):
    def test_fresh_overview_lists_ready_coming_and_broken_dungeons(self):
        overview = self.session().overview()
        rows = overview["dungeons"]
        self.assertEqual(16, len(rows))
        self.assertEqual(["t%02d" % n for n in range(1, 17)], [row["id"] for row in rows])
        self.assertEqual((True, 4, 0, 0.0), (rows[0]["ready"], rows[0]["total"], rows[0]["passed"], rows[0]["progress"]))
        self.assertFalse(rows[1]["ready"])
        self.assertIn("problem.json", rows[1]["error"])
        self.assertEqual((False, ""), (rows[2]["ready"], rows[2]["error"]))
        self.assertTrue(rows[-1]["final"])
        self.assertEqual(1, len(overview["bank_errors"]))
        self.assertTrue(overview["bank_errors"][0].startswith("t02: p1/problem.json 을 읽을 수 없습니다"))
        self.assertEqual((1, 0, 0, 4), (overview["ready"], overview["cleared"], overview["passed"], overview["total"]))
        self.assertEqual({"python": 0, "javascript": 0}, overview["by_lang"])
        self.assertEqual({"did": "t01", "pid": "p1", "no": "1-1", "title": "물통 합계", "role": "basic"}, overview["next"])
        self.assertEqual([], overview["recent"])
        self.assertEqual(14, len(overview["activity"]))
        self.assertEqual(datetime.date.today().isoformat(), list(overview["activity"])[-1])

    def test_mid_alone_opens_the_boss_and_side_is_never_recommended(self):
        journey = self.session()
        with self.assertRaises(JourneyError) as caught:
            journey.problem("t01", "boss", "python")
        self.assertIn("1개 중 0개 통과", str(caught.exception))
        boss_row = journey.dungeon("t01")["problems"][-1]
        self.assertTrue(boss_row["locked"])

        self.write_log([grade_entry("t01/p2")])
        journey = self.session()
        self.assertTrue(journey.overview()["dungeons"][0]["boss_open"])
        self.assertEqual("1-B", journey.problem("t01", "boss", "python")["no"])
        self.assertFalse(journey.dungeon("t01")["problems"][-1]["locked"])
        self.assertEqual("p1", journey.overview()["next"]["pid"])

        self.write_log([grade_entry("t01/p2"), grade_entry("t01/p1")])
        self.assertEqual("boss", self.session().overview()["next"]["pid"])

    def test_counts_recent_activity_and_clear(self):
        self.write_log([
            grade_entry("t01/p1", "python"),
            grade_entry("t01/p1", "javascript"),
            entry("hint", "t01/p2", level=1),
            entry("hint", "t01/p2", level=2),
            grade_entry("t01/p2", "python", passed=False, score=55.0),
            entry("explain", "t01/p2"),
            grade_entry("t01/p2", "python"),
            grade_entry("t01/boss", "javascript"),
        ])
        overview = self.session().overview()
        self.assertEqual((1, 3, 4), (overview["cleared"], overview["passed"], overview["total"]))
        self.assertEqual({"python": 2, "javascript": 2}, overview["by_lang"])
        self.assertEqual((1, 2, 5), (overview["explained_first"], overview["hints"], overview["attempts"]))
        self.assertEqual(["t01/boss", "t01/p2", "t01/p2", "t01/p1", "t01/p1"], [row["item"] for row in overview["recent"]])
        self.assertEqual(("1-B", "물통 정리", "javascript"), tuple(overview["recent"][0][k] for k in ("no", "title", "lang")))
        self.assertEqual(5, overview["activity"][datetime.date.today().isoformat()])
        self.assertIsNone(overview["next"])
        self.assertTrue(overview["dungeons"][0]["cleared"])
        self.assertEqual(0.75, overview["dungeons"][0]["progress"])

        rows = {row["id"]: row for row in self.session().dungeon("t01")["problems"]}
        self.assertEqual(["python", "javascript"], rows["p1"]["passed_langs"])
        self.assertEqual({"python": 100.0}, rows["p2"]["best"])
        self.assertTrue(rows["p2"]["explained_first"])
        self.assertFalse(rows["p1"]["explained_first"])
        self.assertEqual((2, 2), (rows["p2"]["attempts"], rows["p2"]["hints"]))
        self.assertEqual(("선택", False), (rows["p3"]["role_label"], rows["p3"]["tried"]))
        self.assertEqual([{"pid": "p1", "no": "1-1", "title": "물통 합계", "passed": True}], rows["p2"]["prep"])

    def test_boss_new_appears_only_after_boss_pass_or_boss_explain(self):
        detail = self.session().dungeon("t01")
        self.assertIsNone(detail["boss_new"])
        self.assertEqual(["배열 합", "최댓값 찾기", "문자열 뒤집기"], detail["skills"])
        self.assertEqual((0, 1), (detail["mid_passed"], detail["mid_total"]))
        self.write_log([grade_entry("t01/p2"), entry("explain", "t01/boss")])
        self.assertEqual("정렬한 뒤 앞에서 k개를 골라 더함", self.session().dungeon("t01")["boss_new"])
        self.write_log([grade_entry("t01/p2"), grade_entry("t01/boss")], user="bob")
        detail = self.session("bob").dungeon("t01")
        self.assertEqual("정렬한 뒤 앞에서 k개를 골라 더함", detail["boss_new"])
        self.assertTrue(detail["cleared"])
        self.assertEqual(["배열 합", "최댓값 찾기", "문자열 뒤집기"], detail["skills"])

    def test_coming_and_unknown_dungeons(self):
        journey = self.session()
        detail = journey.dungeon("t03")
        self.assertEqual((False, [], "준비 중 던전 3"), (detail["ready"], detail["problems"], detail["title"]))
        with self.assertRaises(JourneyError):
            journey.dungeon("t99")
        with self.assertRaises(JourneyError):
            journey.problem("t03", "p1", "python")
        with self.assertRaises(JourneyError):
            journey.problem("t02", "p1", "python")
        with self.assertRaises(JourneyError):
            journey.problem("t01", "p7", "python")
        with self.assertRaises(JourneyError):
            journey.problem("t01", "p1", "ruby")


@SKIP_LEAN
class ProgressFileTest(Base):
    def test_progress_file_follows_the_record_format(self):
        journey = self.session()
        self.assertFalse(os.path.exists(self.progress_path()))
        journey.reveal_hint("t01", "p1")
        text = study.read_text(self.progress_path())
        data = json.loads(text)
        self.assertEqual(json.dumps(data, ensure_ascii=False, indent=1) + "\n", text)
        self.assertEqual(["format", "user", "created", "log"], list(data))
        self.assertEqual((1, "alice"), (data["format"], data["user"]))
        self.assertEqual(["at", "kind", "item", "level"], list(data["log"][0]))
        self.assertEqual(("hint", "t01/p1", 1), (data["log"][0]["kind"], data["log"][0]["item"], data["log"][0]["level"]))
        datetime.datetime.strptime(data["log"][0]["at"], "%Y-%m-%dT%H:%M:%S")

    def test_broken_progress_file_is_a_journey_error(self):
        for text in ("{not json", '{"format": 1}', '{"log": [3]}', '{"log": {"a": 1}}'):
            study.write_text(self.progress_path(), text)
            with self.assertRaises(JourneyError) as caught:
                self.session()
            self.assertIsInstance(caught.exception, session.SessionError)
            self.assertIn("journey/progress.json", str(caught.exception))

    def test_write_rereads_records_made_by_another_session(self):
        first, second = self.session(), self.session()
        first.reveal_hint("t01", "p1")
        self.assertEqual(2, second.reveal_hint("t01", "p1")["level"])
        self.assertEqual([1, 2], [e["level"] for e in self.read_log()])

    def test_bad_user_is_rejected(self):
        with self.assertRaises(JourneyError):
            JourneySession("../alice")


@SKIP_LEAN
class HintTest(Base):
    def test_hints_open_in_order_until_none_are_left(self):
        journey = self.session()
        first = journey.reveal_hint("t01", "p1")
        self.assertEqual((1, 2), (first["level"], first["left"]))
        self.assertIn("한 변수에 모아", first["text"])
        second = journey.reveal_hint("t01", "p1")
        self.assertEqual((2, 1), (second["level"], second["left"]))
        self.assertIn("0으로 시작", second["text"])
        shown = journey.problem("t01", "p1", "python")
        self.assertEqual((3, [first["text"], second["text"]]), (shown["hint_total"], shown["hints"]))
        self.assertEqual(0, journey.reveal_hint("t01", "p1")["left"])
        with self.assertRaises(JourneyError):
            journey.reveal_hint("t01", "p1")
        self.assertEqual([1, 2, 3], [e["level"] for e in self.read_log()])
        self.assertEqual(2, journey.problem("t01", "p3", "python")["hint_total"])

    def test_locked_boss_hints_are_refused(self):
        with self.assertRaises(JourneyError):
            self.session().reveal_hint("t01", "boss")
        self.assertEqual([], self.read_log())


@SKIP_LEAN
class CodeTest(Base):
    def code_path(self, pid, ext):
        return os.path.join(study.SUBMISSIONS_DIR, "alice", "journey", "t01", pid + ext)

    def test_starter_code_is_not_saved_and_reset_restores_it(self):
        journey = self.session()
        starter = values.starter(journey.dungeons["t01"]["problems"][0]["signature"], "python")
        shown = journey.problem("t01", "p1", "python")
        self.assertEqual((starter, starter, "solution.py"), (shown["code"], shown["starter"], shown["file_name"]))
        journey.save_code("t01", "p1", "python", starter)
        self.assertFalse(os.path.exists(self.code_path("p1", ".py")))
        journey.save_code("t01", "p1", "python", "def solution(nums):\r\n    return 1\r\n")
        self.assertEqual("def solution(nums):\n    return 1\n", study.read_text(self.code_path("p1", ".py")))
        self.assertEqual("def solution(nums):\n    return 1\n", journey.problem("t01", "p1", "python")["code"])
        self.assertEqual(starter, journey.reset_code("t01", "p1", "python"))
        self.assertEqual(starter, study.read_text(self.code_path("p1", ".py")))
        js = journey.reset_code("t01", "p1", "javascript")
        self.assertTrue(js.startswith("function solution(nums) {"))
        self.assertFalse(os.path.exists(self.code_path("p1", ".js")))
        self.assertEqual("solution.js", journey.problem("t01", "p1", "javascript")["file_name"])

    def test_save_cases_checks_each_case(self):
        journey = self.session()
        cases = [{"args": [[1, 2]], "expected": 3}, {"args": [[5]], "expected": 5}]
        self.assertEqual(cases, journey.save_cases("t01", "p1", cases))
        self.assertEqual({"cases": cases}, study.read_json(os.path.join(study.SUBMISSIONS_DIR, "alice", "journey", "t01", "p1.cases.json")))
        self.assertEqual(cases, journey.problem("t01", "p1", "python")["cases"])
        wrong = [
            ([{"args": [[1], 2], "expected": 3}], "1번 케이스의 인자가 1개여야 합니다."),
            ([cases[0], {"args": [["a"]], "expected": 1}], "2번 케이스의 nums 칸: "),
            ([{"args": [[True]], "expected": 1}], "1번 케이스의 nums 칸: "),
            ([{"args": [[1]], "expected": "1"}], "1번 케이스의 기댓값 칸: "),
            ([{"args": [[1]]}], "1번 케이스의 기댓값 칸이 비어 있습니다."),
            ([cases[0]] * 21, "20개까지"),
        ]
        for given, message in wrong:
            with self.assertRaises(JourneyError) as caught:
                journey.save_cases("t01", "p1", given)
            self.assertIn(message, str(caught.exception))
        self.assertEqual(cases, journey.problem("t01", "p1", "python")["cases"])
        self.assertEqual([], journey.save_cases("t01", "p1", []))
        self.assertEqual([], journey.problem("t01", "p1", "python")["cases"])


@SKIP_LEAN
class ExplainTest(Base):
    def test_give_up_opens_and_records_then_a_pass_counts_as_explained_first(self):
        journey = self.session()
        self.assertFalse(journey.problem("t01", "p1", "python")["explain_open"])
        with self.assertRaises(JourneyError):
            journey.open_explain("t01", "p1", "python")
        self.assertEqual([], self.read_log())
        opened = journey.open_explain("t01", "p1", "python", give_up=True)
        self.assertEqual(["explain"], [e["kind"] for e in self.read_log()])
        self.assertEqual(read_fixture("p1/explain.md"), opened["markdown"])
        self.assertEqual({"python": read_fixture("p1/solution.py"), "javascript": read_fixture("p1/solution.js")},
                         opened["solution"])
        self.assertEqual([{"site": "boj", "title": "A+B", "id": 1000, "fit": "easy", "url": "https://www.acmicpc.net/problem/1000"}],
                         opened["similar"])
        self.assertEqual([], opened["parts"])
        self.assertEqual(os.path.join(FIXTURE, "t01"), opened["base_dir"])
        journey.open_explain("t01", "p1", "python")
        self.assertEqual(1, len(self.read_log()))
        self.assertTrue(journey.problem("t01", "p1", "python")["explain_open"])

        self.write_log(self.read_log() + [grade_entry("t01/p1")])
        journey = self.session()
        self.assertTrue(journey.problem("t01", "p1", "python")["explained_first"])
        self.assertEqual(1, journey.overview()["explained_first"])

    def test_passed_problem_opens_without_a_record_and_boss_parts_come_from_extra(self):
        self.write_log([grade_entry("t01/p2"), grade_entry("t01/boss")])
        journey = self.session()
        opened = journey.open_explain("t01", "boss", "javascript")
        self.assertEqual(2, len(self.read_log()))
        self.assertEqual([{"text": "배열을 한 번 훑으며 값을 더함", "from": ["p1"], "nos": ["1-1"]},
                          {"text": "큰 값부터 고름", "from": ["p2"], "nos": ["1-2"]}], opened["parts"])
        self.assertEqual(["https://school.programmers.co.kr/learn/courses/30/lessons/42748", "https://www.acmicpc.net/problem/2750"],
                         [row["url"] for row in opened["similar"]])
        programmers = journey.open_explain("t01", "p3", "python", give_up=True)["similar"]
        self.assertEqual([None], [row["url"] for row in programmers])
        self.assertFalse(journey.dungeon("t01")["problems"][-1]["explained_first"])


@SKIP_LEAN
class RuntimeTest(Base):
    def test_making_a_session_does_not_look_for_node(self):
        with mock.patch.object(node, "find", side_effect=AssertionError("node.find")) as find, \
                mock.patch.object(node, "search", side_effect=AssertionError("node.search")) as search:
            journey = JourneySession("alice", node_path="/없는/node")
            journey.overview()
            journey.dungeon("t01")
            journey.problem("t01", "p1", "python")
            journey.problem("t01", "p1", "javascript")
            self.assertTrue(journey.runtime("python")["ok"])
        find.assert_not_called()
        search.assert_not_called()

    def test_runtime_reports_missing_and_found_node(self):
        journey = JourneySession("alice", node_path="/고른/node")
        with mock.patch.object(node, "find", return_value=None) as find:
            missing = journey.runtime("javascript")
        find.assert_called_once_with(saved="/고른/node")
        self.assertFalse(missing["ok"])
        self.assertIn("Node.js 20 이상", missing["problem"])
        with mock.patch.object(node, "find", return_value={"path": "/x/node", "version": "22.1.0", "major": 22}):
            found = journey.runtime("javascript")
        self.assertEqual((True, "Node.js 22.1.0"), (found["ok"], found["label"]))
        with mock.patch.object(node, "find", return_value=None):
            with self.assertRaises(JourneyError):
                journey.run("t01", "p1", "javascript")
        self.assertTrue(journey.runtime("python")["label"].startswith("Python 3."))

    def test_set_node_rejects_a_bad_file_and_find_node_forgets_first(self):
        journey = self.session()
        with self.assertRaises(JourneyError):
            journey.set_node(os.path.join(self.tmp.name, "없는 파일"))
        with mock.patch.object(node, "forget") as forget, mock.patch.object(node, "find", return_value=None) as find:
            self.assertFalse(journey.find_node(probe=False)["ok"])
        forget.assert_called_once_with()
        self.assertEqual(mock.call(probe=False, saved=None), find.call_args_list[0])

    def test_runner_errors_become_journey_errors(self):
        journey = self.session()
        with mock.patch.object(runner.subprocess, "Popen", side_effect=OSError("실행 파일이 없음")):
            with self.assertRaises(JourneyError) as caught:
                journey.run("t01", "p1", "python")
        self.assertIn("코드를 실행하지 못했습니다. 실행 파일이 없음", str(caught.exception))
        with mock.patch.object(runner, "command", side_effect=RuntimeError("Node.js 를 찾지 못했습니다.")):
            with self.assertRaises(JourneyError) as caught:
                journey.grade("t01", "p1", "python")
        self.assertIn("채점하지 못했습니다. Node.js 를 찾지 못했습니다.", str(caught.exception))
        self.assertEqual([], self.read_log())

    def test_cache_info_and_clear_cache(self):
        journey = self.session()
        self.assertEqual({"bytes": 0, "files": 0}, journey.cache_info())
        study.write_text(os.path.join(runner.CACHE_DIR, "a.json"), "[[1]]")
        study.write_text(os.path.join(runner.CACHE_DIR, "b.json"), "[[22]]")
        self.assertEqual({"bytes": 11, "files": 2}, journey.cache_info())
        self.assertEqual({"bytes": 0, "files": 0}, journey.clear_cache())


@SKIP_LEAN
class GradingRulesTest(unittest.TestCase):
    def test_labels_follow_the_result_table(self):
        self.assertEqual("통과 (0.42ms, 10.3MB)", grading.label("pass", 0.4213, 10.31))
        self.assertEqual("실패 (0.02ms, 10.2MB)", grading.label("wrong", 0.02, 10.2))
        self.assertEqual("실패 (0.02ms, 10.2MB)", grading.label("bad_return", 0.02, 10.2))
        self.assertEqual("실패 (시간 초과)", grading.label("timeout", 3000.0, 20.0))
        self.assertEqual("실패 (메모리 초과)", grading.label("memory"))
        self.assertEqual("실패 (런타임 에러)", grading.label("runtime", 1.0, 2.0))
        self.assertEqual("취소됨", grading.label("cancelled", count=50))
        self.assertEqual("통과 (0.42ms, 15.3MB) · 50건", grading.label("pass", 0.42, 15.3, 50))
        self.assertEqual("실패 (시간 초과) · 50건", grading.label("timeout", count=50))

    def test_points_and_rounding(self):
        problem = {"score": None}
        self.assertEqual((70.0, 30.0), grading.points(problem, "basic", True))
        self.assertEqual((60.0, 40.0), grading.points(problem, "side", True))
        self.assertEqual((50.0, 50.0), grading.points(problem, "boss", True))
        self.assertEqual((100.0, 0.0), grading.points(problem, "boss", False))
        self.assertEqual((80.0, 20.0), grading.points({"score": {"accuracy": 80, "efficiency": 20}}, "mid", True))
        self.assertEqual((56.3, 16.7, 43.3), (grading.round1(56.25), grading.round1(50 / 3), grading.round1(70 * 13 / 21)))
        self.assertEqual("채점에서는 Python 3초, JavaScript 3.5초 안에 끝나야 합니다.",
                         grading.limit_note({"time_limit_ms": {"python": 3000, "javascript": 3500}}))

    def test_a_test_without_expected_value_is_refused(self):
        with self.assertRaises(bank.BankError) as caught:
            grading.make_case({"id": "loose", "args": [[1]]}, None, 1000, 1500)
        self.assertIn("loose 에 expected 도 expected_sha 도 없습니다", str(caught.exception))
        self.assertEqual("abc", grading.make_case({"id": "a", "args": [[1]], "expected_sha": "abc"}, None, 1000, 1500)["expected_sha"])

    def test_efficiency_tests_follow_langs(self):
        tests = {"efficiency": [{"id": "a"}, {"id": "b", "langs": ["python"]}, {"id": "c", "langs": ["javascript"]}]}
        self.assertEqual(["a", "b"], [t["id"] for t in grading.efficiency_tests(tests, "python")])
        self.assertEqual(["a", "c"], [t["id"] for t in grading.efficiency_tests(tests, "javascript")])


@SKIP_LEAN
class GradeTest(Base):
    def save(self, journey, pid, rel, lang="python"):
        journey.save_code("t01", pid, lang, read_fixture(rel))

    def test_full_grade_records_one_line_and_opens_the_boss(self):
        journey = self.session()
        self.save(journey, "p2", "p2/solution.py")
        events = []
        result = journey.grade("t01", "p2", "python", report=events.append)
        self.assertEqual((True, 100.0, 80.0, 20.0), (result["passed"], result["score"], result["acc"], result["eff"]))
        self.assertEqual((True, True, False), (result["first_pass"], result["boss_opened"], result["cleared"]))
        self.assertIsNone(result["fatal"])
        self.assertTrue(result["runtime"].startswith("Python 3."))
        self.assertEqual([("정확성", 80.0, 18), ("효율성", 20.0, 4)],
                         [(g["name"], g["points"], len(g["cases"])) for g in result["groups"]])
        accuracy = result["groups"][0]["cases"]
        self.assertEqual(["ex1", "ex2", "ex3"], [c["id"] for c in accuracy[:3]])
        self.assertEqual(list(range(1, 19)), [c["no"] for c in accuracy])
        self.assertTrue(accuracy[-1]["label"].startswith("통과 (") and accuracy[-1]["label"].endswith("MB) · 50건"))
        self.assertEqual(50, accuracy[-1]["count"])
        self.assertTrue(all(c["name"] is None for c in accuracy))
        cases = [e for e in events if e["kind"] == "case"]
        self.assertEqual([("정확성", n) for n in range(1, 19)] + [("효율성", n) for n in range(1, 5)],
                         [(e["group"], e["case"]["no"]) for e in cases])
        self.assertIn(grading.GEN_TEXT, [e["text"] for e in events if e["kind"] == "status"])
        log = self.read_log()
        self.assertEqual(1, len(log))
        self.assertEqual({"kind": "grade", "item": "t01/p2", "lang": "python", "score": 100.0, "acc": 80.0, "eff": 20.0,
                          "passed": True, "tests": [18, 18, 4, 4]}, {k: v for k, v in log[0].items() if k != "at"})
        self.assertTrue(journey.overview()["dungeons"][0]["boss_open"])
        events = []
        again = journey.grade("t01", "p2", "python", report=events.append)
        self.assertEqual((True, False, False), (again["passed"], again["first_pass"], again["boss_opened"]))
        self.assertNotIn(grading.GEN_TEXT, [e["text"] for e in events if e["kind"] == "status"])
        self.assertEqual(2, len(self.read_log()))

    def test_cancelled_grade_records_nothing(self):
        journey = self.session()
        self.save(journey, "p1", "p1/solution.py")
        cancel = threading.Event()

        def report(event):
            if event["kind"] == "case":
                cancel.set()

        result = journey.grade("t01", "p1", "python", report=report, cancel=cancel)
        self.assertTrue(result["cancelled"])
        self.assertFalse(result["passed"])
        self.assertEqual([], self.read_log())

    def test_fatal_grade_scores_zero_and_records_the_kind(self):
        journey = self.session()
        journey.save_code("t01", "p1", "python", SYNTAX_ERROR)
        events = []
        result = journey.grade("t01", "p1", "python", report=events.append)
        self.assertEqual(("syntax", 0.0, False, []), (result["fatal"]["kind"], result["score"], result["passed"], result["groups"]))
        self.assertEqual(2, result["fatal"]["line"])
        self.assertEqual([], [e for e in events if e["kind"] == "case"])
        log = self.read_log()
        self.assertEqual(("syntax", 0.0, False, [0, 18, 0, 3]), (log[0]["fatal"], log[0]["score"], log[0]["passed"], log[0]["tests"]))

    def test_fatal_after_the_first_case_is_a_runtime_line(self):
        journey = self.session()
        journey.save_code("t01", "p1", "python", FAILS_AFTER_FIRST)
        events = []
        result = journey.grade("t01", "p1", "python", report=events.append)
        self.assertIsNone(result["fatal"])
        accuracy, efficiency = result["groups"]
        self.assertEqual(["pass"] + ["runtime"] * 17, [c["status"] for c in accuracy["cases"]])
        self.assertEqual(["runtime"] * 3, [c["status"] for c in efficiency["cases"]])
        self.assertEqual("실패 (런타임 에러)", accuracy["cases"][1]["label"])
        self.assertEqual([("정확성", n) for n in range(1, 19)] + [("효율성", n) for n in range(1, 4)],
                         [(e["group"], e["case"]["no"]) for e in events if e["kind"] == "case"])
        self.assertEqual(([1, 18, 0, 3], 3.9), (result["tests"], result["score"]))
        self.assertNotIn("fatal", self.read_log()[0])
        run = journey.run("t01", "p1", "python")
        self.assertIsNone(run["fatal"])
        self.assertEqual(["pass", "runtime", "runtime"], [c["status"] for c in run["cases"]])
        self.assertIn("ValueError: 두 번째 프로세스", run["cases"][1]["error"])

    def test_generated_inputs_are_found_when_the_temp_folder_is_reached_through_a_link(self):
        # macOS 의 /var 처럼 임시 폴더가 링크를 거쳐도 케이스 폴더에서 캐시 입력까지 찾아가는지 봄
        real = os.path.join(os.path.realpath(self.tmp.name), "real", "deep")
        os.makedirs(real)
        link = os.path.join(self.tmp.name, "link")
        try:
            os.symlink(real, link, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("심볼릭 링크를 만들 수 없음")
        journey = self.session()
        self.save(journey, "p1", "p1/solution.py")
        with mock.patch.object(tempfile, "tempdir", link):
            result = journey.grade("t01", "p1", "python")
        self.assertEqual(([18, 18, 3, 3], True), (result["tests"], result["passed"]))

    def test_unfilled_tests_file_is_refused_before_running(self):
        path = self.copy_bank()
        tests_path = os.path.join(path, "t01", "p1", "tests.json")
        tests = study.read_json(tests_path)
        del tests["efficiency"][0]["expected"]
        study.write_text(tests_path, json.dumps(tests, ensure_ascii=False))
        events = []
        with mock.patch.object(bank, "BANK_DIR", path):
            journey = self.session()
            with self.assertRaises(JourneyError) as caught:
                journey.grade("t01", "p1", "python", report=events.append)
        self.assertIn("채점 파일이 올바르지 않습니다", str(caught.exception))
        self.assertEqual(([], []), (events, self.read_log()))

    def test_names_of_failed_accuracy_tests_appear_only_after_the_explanation_opens(self):
        journey = self.session()
        self.save(journey, "p1", "p1/wrong/first_only.py")
        hidden = journey.grade("t01", "p1", "python")
        self.assertFalse(hidden["passed"])
        self.assertTrue(all(c["name"] is None for g in hidden["groups"] for c in g["cases"]))
        journey.open_explain("t01", "p1", "python", give_up=True)
        shown = journey.grade("t01", "p1", "python")
        accuracy, efficiency = shown["groups"]
        names = {c["id"]: c["name"] for c in accuracy["cases"]}
        self.assertEqual(("입출력 예 1", "양수와 음수가 섞임"), (names["ex1"], names["mixed"]))
        self.assertIsNone(names["ex3"])
        self.assertTrue(all(c["status"] != "pass" for c in efficiency["cases"]))
        self.assertTrue(all(c["name"] is None for c in efficiency["cases"]))
        self.assertEqual(shown["tests"], [4, 18, 0, 3])

    def test_boss_clear_and_starter_code_without_a_file(self):
        self.write_log([grade_entry("t01/p2")])
        journey = self.session()
        starter = journey.grade("t01", "boss", "python")
        self.assertFalse(starter["passed"])
        self.save(journey, "boss", "boss/solution.py")
        cleared = journey.grade("t01", "boss", "python")
        self.assertEqual((True, True, True, 50.0), (cleared["passed"], cleared["first_pass"], cleared["cleared"], cleared["acc"]))
        self.assertEqual("정렬한 뒤 앞에서 k개를 골라 더함", journey.dungeon("t01")["boss_new"])
        self.assertEqual((1, None), (journey.overview()["cleared"], journey.overview()["next"]))

    def test_run_shows_examples_and_my_cases_without_recording(self):
        journey = self.session()
        result = journey.run("t01", "p1", "python")
        self.assertEqual((0, 3, False), (result["passed"], result["total"], result["cancelled"]))
        self.assertEqual(("[1, 2, 3]", "6", "0", "wrong"), tuple(result["cases"][0][k] for k in ("args_text", "want_text", "got_text", "status")))
        self.assertEqual("채점에서는 Python 2초, JavaScript 1초 안에 끝나야 합니다.", result["limit_note"])
        journey.save_cases("t01", "p1", [{"args": [[2, 2]], "expected": 4}])
        journey.save_code("t01", "p1", "python", "def solution(nums):\n    print('합', len(nums))\n    return sum(nums)\n")
        events = []
        result = journey.run("t01", "p1", "python", report=events.append)
        self.assertEqual((4, 4), (result["passed"], result["total"]))
        self.assertEqual(["example", "example", "example", "mine"], [c["source"] for c in result["cases"]])
        self.assertEqual("합 2\n", result["cases"][3]["printed"])
        self.assertEqual(4, len([e for e in events if e["kind"] == "case"]))
        journey.save_code("t01", "p1", "python", SYNTAX_ERROR)
        fatal = journey.run("t01", "p1", "python")
        self.assertEqual(("syntax", 2, []), (fatal["fatal"]["kind"], fatal["fatal"]["line"], fatal["cases"]))
        self.assertEqual([], self.read_log())

    def test_run_clips_long_output(self):
        journey = self.session()
        journey.save_code("t01", "p1", "python", "def solution(nums):\n    for i in range(300):\n        print(i)\n    return sum(nums)\n")
        case = journey.run("t01", "p1", "python")["cases"][0]
        self.assertTrue(case["printed_cut"])
        self.assertEqual(grading.PRINT_LINES, len(case["printed"].split("\n")))

    @unittest.skipUnless(NODE, "Node.js 20 이상이 없음")
    def test_javascript_grade_uses_only_its_efficiency_tests(self):
        journey = self.session()
        self.save(journey, "p2", "p2/solution.js", "javascript")
        result = journey.grade("t01", "p2", "javascript")
        self.assertTrue(result["passed"])
        self.assertTrue(result["runtime"].startswith("Node.js "))
        self.assertEqual([18, 3], [len(g["cases"]) for g in result["groups"]])
        self.assertEqual([18, 18, 3, 3], self.read_log()[0]["tests"])
        self.assertEqual(["javascript"], journey.dungeon("t01")["problems"][1]["passed_langs"])
        self.save(journey, "boss", "boss/wrong/default_sort.js", "javascript")
        wrong = journey.grade("t01", "boss", "javascript")
        failed = [c["id"] for c in wrong["groups"][0]["cases"] if c["status"] != "pass"]
        self.assertIn("long", failed)
        run = journey.run("t01", "p3", "javascript")
        self.assertEqual('"abc"', run["cases"][0]["args_text"])


if __name__ == "__main__":
    unittest.main()
