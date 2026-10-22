# -*- coding: utf-8 -*-
"""여행 화면과 첫 화면이 같이 쓰는 글자 도우미(gui/journey_text.py). PyQt 없이 돎.
이어서 할 일 순서는 고정 은행 tests/journey_bank 의 사본(t01 을 t03 자리에도 복사해 준비된 던전이 둘)과 실제 JourneySession 으로 봄.
나머지 글은 서비스 dict 꼴의 값과 dungeons/index.json 의 던전 16개로 봄. 자식 프로세스는 띄우지 않음."""
import json
import os
import re
import shutil
import sys
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("STUDY_NODE_PROBE", "0")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import adaptive  # noqa: E402
import study  # noqa: E402
from gui import journey_text  # noqa: E402
from journey import bank, grading, runner  # noqa: E402
from journey.service import JourneyError, JourneySession, check_lang  # noqa: E402

FIXTURE = os.path.join(ROOT, "tests", "journey_bank")
INDEX = bank.read_index(os.path.join(ROOT, "dungeons"))
NUMBERS = {entry["id"]: entry["no"] for entry in INDEX}
INNER_ID = re.compile(r"(?<![A-Za-z0-9])(d\d\d|t\d\d|p\d|boss)(?![A-Za-z0-9])|\.json")  # 화면 글에 두지 않는 내부 id 와 파일 이름


def grade_entry(item, lang="python", passed=True, score=None):
    score = 100.0 if passed else (40.0 if score is None else score)
    return {"at": adaptive.now(), "kind": "grade", "item": item, "lang": lang, "score": score, "acc": score, "eff": 0.0,
            "passed": passed, "tests": [1, 1, 0, 0]}


def problem_row(no="1-1", role="basic", tier="S3 / Lv2", **fields):
    """dungeon()["problems"] 의 줄과 같은 꼴."""
    row = {"id": "p1", "no": no, "role": role, "role_label": "", "title": "장부 정산", "tier": tier, "passed": False,
           "passed_langs": [], "best": {}, "tried": False, "attempts": 0, "hints": 0, "explained": False,
           "explained_first": False, "locked": False, "prep": []}
    row.update(fields)
    return row


def group(name, earned, points):
    return {"name": name, "earned": earned, "points": points, "cases": []}


class SessionBase(unittest.TestCase):
    """고정 은행의 사본으로 여는 JourneySession. 사본에는 t01 과 같은 던전이 t03 에도 있음."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="journey_text_")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        root = os.path.join(self.tmp, "bank")
        shutil.copytree(FIXTURE, root)
        shutil.copytree(os.path.join(root, "t01"), os.path.join(root, "t03"))
        for target, name, value in ((study, "SUBMISSIONS_DIR", os.path.join(self.tmp, "submissions")),
                                    (runner, "CACHE_DIR", os.path.join(self.tmp, "cache")), (bank, "BANK_DIR", root)):
            patcher = mock.patch.object(target, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def service(self, entries=()):
        if entries:
            data = {"format": 1, "user": "alice", "created": adaptive.now(), "log": list(entries)}
            path = os.path.join(study.SUBMISSIONS_DIR, "alice", "journey", "progress.json")
            study.write_text(path, json.dumps(data, ensure_ascii=False, indent=1) + "\n")
        return JourneySession("alice")


class NextItemTest(SessionBase):
    def pick(self, service, last=""):
        item = journey_text.next_item(service, last)
        return item and (item["did"], item["pid"], item["title"], item["role"])

    def test_without_an_opened_problem_it_follows_the_service(self):
        item = journey_text.next_item(self.service())
        self.assertEqual(item, {"did": "t01", "pid": "p1", "title": "물통 합계", "place": "던전 1 「시험 마을」", "role": "기초",
                                "action": "문제 풀기"})

    def test_passed_problems_side_problems_and_the_locked_boss_are_skipped(self):
        service = self.service([grade_entry("t01/p1")])
        self.assertEqual(self.pick(service), ("t01", "p2", "가장 큰 물통", "중급"))
        self.assertEqual(self.pick(service, "t01/p1"), ("t01", "p2", "가장 큰 물통", "중급"), "통과한 문제는 다시 권하지 않음")
        self.assertEqual(self.pick(service, "t01/boss"), ("t01", "p2", "가장 큰 물통", "중급"), "잠긴 보스는 열 수 없음")
        service = self.service([grade_entry("t01/p1"), grade_entry("t01/p2")])
        self.assertEqual(self.pick(service), ("t01", "boss", "물통 정리", "보스"), "선택 문제 1-3 은 건너뜀")
        self.assertEqual(self.pick(service, "t01/boss"), ("t01", "boss", "물통 정리", "보스"))

    def test_the_last_opened_problem_comes_first(self):
        service = self.service([grade_entry("t01/p1", passed=False)])
        self.assertEqual(self.pick(service, "t01/p3"), ("t01", "p3", "이름 뒤집기", "선택"))
        item = journey_text.next_item(service, "t03/p2")
        self.assertEqual((item["did"], item["pid"], item["place"], item["role"]), ("t03", "p2", "던전 3 「준비 중 던전 3」", "중급"))
        overview = service.overview()
        self.assertEqual(journey_text.next_item(service, "t03/p2", overview), item, "읽어 둔 overview 를 넘겨도 같음")

    def test_a_last_problem_that_cannot_be_opened_falls_back_to_the_service(self):
        service = self.service()
        for last in ("", "t01", "t01/", "t01/p9", "t99/p1", "t02/p1", "t04/p1", "/p1", "아무 글"):
            self.assertEqual(self.pick(service, last), ("t01", "p1", "물통 합계", "기초"), last)

    def test_nothing_left_after_every_boss_is_cleared(self):
        cleared = [grade_entry("%s/%s" % (did, pid)) for did in ("t01", "t03") for pid in ("p1", "p2", "boss")]
        service = self.service(cleared)
        self.assertIsNone(journey_text.next_item(service))
        self.assertEqual(self.pick(service, "t03/p3"), ("t03", "p3", "이름 뒤집기", "선택"), "선택 문제는 마지막으로 열었으면 권함")


class TrackAndDungeonTest(SessionBase):
    def test_track_line_names_the_next_item(self):
        service = self.service([grade_entry("t01/p1")])
        overview = service.overview()
        self.assertEqual(journey_text.track_line(overview, journey_text.next_item(service, "", overview)),
                         "8문제 중 1개 통과 · 다음은 가장 큰 물통")
        self.assertEqual(journey_text.track_line(overview, journey_text.next_item(service, "t03/p3", overview)),
                         "8문제 중 1개 통과 · 다음은 이름 뒤집기")
        self.assertEqual(journey_text.track_line(dict(overview, passed=8), None), "8문제 중 8개 통과 · 모두 클리어했습니다.")
        self.assertEqual(journey_text.track_line({"total": 0, "passed": 0}, None), "0문제 중 0개 통과 · 아직 준비된 던전이 없습니다.")

    def test_map_and_dungeon_counts(self):
        service = self.service([grade_entry("t01/p1"), grade_entry("t01/p2"), grade_entry("t01/boss")])
        overview = service.overview()
        self.assertEqual(journey_text.map_count(overview), "8문제 중 3개 통과 · 클리어 1개")
        self.assertEqual(journey_text.dungeon_count(service.dungeon("t01")), "4문제 중 3개 통과")
        self.assertEqual(journey_text.dungeon_count(service.dungeon("t02")), "", "읽지 못한 던전은 수를 말하지 않음")
        self.assertEqual(journey_text.dungeon_count(service.dungeon("t04")), "")
        self.assertEqual(journey_text.place(service.dungeon("t01")), "던전 1 「시험 마을」")

    def test_dungeon_lines_from_the_index(self):
        entries = {entry["id"]: entry for entry in INDEX}
        self.assertEqual(journey_text.place(entries["d01"]), "던전 1 「향신료 시장」")
        self.assertEqual(journey_text.dungeon_lines(entries["d01"], NUMBERS), ["해시·투 포인터 · 보스 난이도 G3 / Lv3"])
        self.assertEqual(journey_text.dungeon_lines(entries["d04"], NUMBERS),
                         ["구현·시뮬레이션 · 보스 난이도 G2 / Lv3", "던전 1, 2 다음에 풀면 좋습니다."])
        self.assertEqual(journey_text.dungeon_lines(entries["d16"], NUMBERS),
                         ["최종 던전 · 펜윅·세그먼트·오프라인 · 보스 난이도 P5~P4 / Lv4", "던전 3, 8 다음에 풀면 좋습니다."])
        self.assertEqual(journey_text.dungeon_lines(dict(entries["d04"], prereq=["d01", "x9"]), NUMBERS)[1], "던전 1 다음에 풀면 좋습니다.")

    def test_row_lines_from_the_service(self):
        service = self.service([grade_entry("t01/p1", "javascript"), grade_entry("t01/p3", passed=False, score=41.5)])
        info = service.dungeon("t01")
        self.assertEqual([journey_text.row_line(row, info) for row in info["problems"]],
                         ["1-1 · B2 / Lv1 · 통과 · JavaScript", "1-2 · B1 / Lv1 · 준비 문제 1-1", "1-3 · B3 / Lv1 · 최고 41점",
                          "중급 1개를 모두 통과하면 열립니다."])
        opened = self.service([grade_entry("t01/p2")]).dungeon("t01")
        self.assertEqual(journey_text.row_line(opened["problems"][-1], opened), "S5 / Lv2", "보스 줄은 번호를 뺌")


class RowLineTest(unittest.TestCase):
    def test_second_line_order(self):
        info = {"mid_total": 3, "mid_passed": 1}
        rows = [(problem_row(passed=True, passed_langs=["python"]), "1-1 · S3 / Lv2 · 통과 · Python"),
                (problem_row("1-2", passed=True, explained_first=True, passed_langs=["python", "javascript"]),
                 "1-2 · S3 / Lv2 · 해설 보고 통과 · Python, JavaScript"),
                (problem_row("1-3", "mid", "G4 / Lv3", tried=True, best={"python": 40.0, "javascript": 12.5},
                             prep=[{"pid": "p2", "no": "1-2", "title": "", "passed": True}]),
                 "1-3 · G4 / Lv3 · 최고 40점 · 준비 문제 1-2"),
                (problem_row("1-4", "mid", "G4 / Lv3", prep=[{"pid": "p1", "no": "1-1", "title": "", "passed": False}]),
                 "1-4 · G4 / Lv3 · 준비 문제 1-1"),
                (problem_row("1-B", "boss", "G3 / Lv3", tried=True, best={"python": 55.5}), "G3 / Lv3 · 최고 55점"),
                (problem_row("1-B", "boss", "G3 / Lv3", locked=True), "중급 3개를 모두 통과하면 열립니다. 지금 1개 통과했습니다.")]
        for row, want in rows:
            self.assertEqual(journey_text.row_line(row, info), want)
        self.assertEqual(journey_text.row_line(rows[-1][0], {"mid_total": 3, "mid_passed": 0}), "중급 3개를 모두 통과하면 열립니다.")


class ScoreTest(unittest.TestCase):
    def test_result_scores_drop_a_trailing_zero(self):
        for value, want in ((100.0, "100"), (41.5, "41.5"), (70, "70"), (29.5, "29.5"), (12.0, "12"), (0.0, "0"), (None, "0")):
            self.assertEqual(journey_text.score_text(value), want, value)

    def test_list_scores_are_floored(self):
        for value, want in ((41.5, "41"), (40.0, "40"), (99.9, "99"), (100.0, "100"), (None, "0")):
            self.assertEqual(journey_text.whole_score(value), want, value)


class TierTipTest(unittest.TestCase):
    def test_every_form_in_the_index(self):
        cases = (("S3 / Lv2", False, "백준 실버 3, 프로그래머스 레벨 2 수준입니다."),
                 ("G3 / Lv3", True, "보스 문제는 백준 골드 3, 프로그래머스 레벨 3 수준입니다."),
                 ("G3 / Lv3~4", True, "보스 문제는 백준 골드 3, 프로그래머스 레벨 3~4 수준입니다."),
                 ("G2 / Lv3 상", True, "보스 문제는 백준 골드 2, 프로그래머스 레벨 3 상위 수준입니다."),
                 ("G1~P5 / Lv4", False, "백준 골드 1~플래티넘 5, 프로그래머스 레벨 4 수준입니다."),
                 ("P5~P4 / Lv4", True, "보스 문제는 백준 플래티넘 5~4, 프로그래머스 레벨 4 수준입니다."),
                 ("B2 / Lv1", False, "백준 브론즈 2, 프로그래머스 레벨 1 수준입니다."))
        for tier, boss, want in cases:
            self.assertEqual(journey_text.tier_tip(tier, boss), want, tier)
        for entry in INDEX:
            self.assertTrue(journey_text.tier_tip(entry["boss_target"], True), entry["boss_target"])

    def test_every_problem_tier_in_the_bank(self):
        root = os.path.join(ROOT, "dungeons")
        tiers = [problem["tier"] for entry in INDEX if bank.is_ready(entry["id"], root)
                 for problem in bank.load_dungeon(entry, root)["problems"]]
        self.assertTrue(tiers)
        for tier in tiers:
            self.assertTrue(journey_text.tier_tip(tier), tier)

    def test_unknown_forms_have_no_tip(self):
        for tier in ("", None, "S3", "Lv2", "X1 / Lv2", "S6 / Lv2", "S3 / Lv9", "S3 / 2"):
            self.assertEqual(journey_text.tier_tip(tier), "", tier)


class ResultHeadTest(unittest.TestCase):
    def head(self, *args, **kwargs):
        head = journey_text.result_head(*args, **kwargs)
        return head["title"], head["bar"], head["caption"]

    def test_before_any_result(self):
        self.assertEqual(self.head(), ("아직 실행하지 않았습니다.", None, "[코드 실행]을 누르면 결과가 여기에 나옵니다."))
        self.assertEqual(self.head(mine=3)[2], "[코드 실행]은 입출력 예와 내 테스트 3개를 돌립니다.")
        self.assertEqual(self.head(best=41.5, mine=3)[2], "지금까지 최고 점수는 100점 중 41.5점입니다.", "기록이 내 테스트보다 먼저")
        self.assertEqual(self.head(best=0.0)[2], "지금까지 최고 점수는 100점 중 0점입니다.")
        self.assertEqual(journey_text.result_head()["banners"], [])

    def test_run(self):
        live = {"cases": [{"no": 1}], "total": 3}
        self.assertEqual(self.head("run", live, done=False), ("실행 중", (1, 3), "테스트 3개 중 1개 끝남"))
        self.assertEqual(self.head("run", {"cases": [], "total": 3}, done=False), ("실행 중", (0, 3), "테스트 3개 중 0개 끝남"))
        failed = {"cases": [{}] * 3, "passed": 1, "total": 3, "fatal": None, "cancelled": False}
        self.assertEqual(self.head("run", failed), ("테스트 3개 중 1개 통과", (1, 3), "고친 뒤 다시 실행하세요."))
        self.assertEqual(journey_text.result_head("run", failed)["tone"], "")
        passed = dict(failed, passed=3)
        self.assertEqual(self.head("run", passed), ("테스트 3개 중 3개 통과", (3, 3), "[채점하기]로 숨은 테스트까지 채점하세요."))
        self.assertEqual(journey_text.result_head("run", passed)["tone"], "success")
        fatal = dict(failed, cases=[], passed=0, fatal={"kind": "syntax", "message": "SyntaxError", "line": 3})
        self.assertEqual(self.head("run", fatal), ("코드를 불러오지 못했습니다", None, "3번째 줄을 확인하세요."))
        self.assertEqual(self.head("run", dict(fatal, fatal={"kind": "load", "message": "", "line": None})),
                         ("코드를 불러오지 못했습니다", None, ""))
        self.assertEqual(self.head("run", dict(failed, cancelled=True)), ("실행을 멈췄습니다", None, "끝난 테스트까지만 보입니다."))

    def test_grade_in_progress(self):
        self.assertEqual(self.head("grade", {"groups": []}, done=False), ("채점 중", "busy", "채점을 준비하는 중입니다."))
        self.assertEqual(self.head("grade", {}, done=False, stage=grading.ACC_TEXT, seconds=12),
                         ("채점 중", "busy", "정확성 테스트를 채점하는 중입니다. 12초 지났습니다."))
        self.assertEqual(self.head("grade", {}, done=False, stage=grading.EFF_TEXT)[2], grading.EFF_TEXT)
        self.assertEqual(self.head("grade", {}, done=False, stage=grading.GEN_TEXT, seconds=75)[2],
                         grading.GEN_TEXT + " 1분 15초 지났습니다.")

    def test_grade_done(self):
        result = {"fatal": None, "cancelled": False, "score": 41.5, "passed": False, "first_pass": False, "boss_opened": False,
                  "groups": [group("정확성", 29.5, 70.0), group("효율성", 12.0, 30.0)]}
        self.assertEqual(self.head("grade", result), ("100점 중 41.5점", (41.5, 100.0), "정확성 29.5 / 70 · 효율성 12 / 30"))
        self.assertEqual(journey_text.result_head("grade", result)["tone"], "")
        first = dict(result, score=100.0, passed=True, first_pass=True, groups=[group("정확성", 70.0, 70.0), group("효율성", 30.0, 30.0)])
        head = journey_text.result_head("grade", first)
        self.assertEqual((head["title"], head["caption"], head["tone"]), ("100점 중 100점", "정확성 70 / 70 · 효율성 30 / 30", "success"))
        self.assertEqual(head["banners"], [("처음으로 통과했습니다. 해설이 열렸습니다.", "해설 보기", "explain")])
        self.assertEqual(journey_text.result_head("grade", dict(first, boss_opened=True))["banners"][1],
                         ("보스 문제가 열렸습니다.", "보스 풀기", "boss"))
        only = dict(first, first_pass=False, groups=[group("정확성", 100.0, 100.0)])
        self.assertEqual(self.head("grade", only)[2], "정확성 100 / 100")
        self.assertEqual(journey_text.result_head("grade", only)["banners"], [], "이미 통과한 문제는 띠가 없음")

    def test_grade_failed_or_stopped(self):
        fatal = {"fatal": {"kind": "syntax", "message": "SyntaxError", "line": 3}, "cancelled": False, "groups": [], "score": 0.0}
        self.assertEqual(self.head("grade", fatal), ("코드를 불러오지 못했습니다", None, "0점으로 기록했습니다. 3번째 줄을 확인하세요."))
        self.assertEqual(self.head("grade", dict(fatal, fatal={"kind": "load", "line": None}))[2], "0점으로 기록했습니다.")
        stopped = {"fatal": None, "cancelled": True, "groups": [group("정확성", 0.0, 70.0)], "score": 0.0}
        self.assertEqual(self.head("grade", stopped), ("채점을 멈췄습니다", None, "이번 채점은 기록에 남지 않습니다."))


class DialogTextTest(SessionBase):
    def test_clear_text_needs_no_particle_after_any_name(self):
        names = [entry["title"] for entry in INDEX]
        self.assertEqual(journey_text.clear_text(names[0], names[1]),
                         "「향신료 시장」 던전을 클리어했습니다. 다음은 「용암 평원」 던전입니다.")
        self.assertEqual(journey_text.clear_text(names[2]), "「모래시계 탑」 던전을 클리어했습니다. 준비된 던전을 모두 클리어했습니다.")
        for name, following in zip(names, names[1:] + [None]):
            text = journey_text.clear_text(name, following)
            self.assertTrue(text.startswith("「%s」 던전을 " % name), text)
            self.assertIsNone(re.search(r"」[을를이가은는]", text), text)

    def test_bank_banner_names_the_dungeon_and_keeps_the_original_in_the_tip(self):
        text, tip = journey_text.bank_text(self.service().overview())
        self.assertEqual(text, "읽지 못한 던전이 있습니다: 던전 2. 첫 화면의 [새 문제 받기]로 다시 받은 뒤 여세요.")
        self.assertIn("t02: ", tip)
        self.assertEqual(journey_text.bank_text({"dungeons": [{"no": 1, "error": ""}], "bank_errors": []}), ("", ""))

    def test_error_text_hides_inner_ids(self):
        refetch = journey_text.REFETCH
        for message in ("문제 d01/p1 를 찾을 수 없습니다.", "던전 d01 를 찾을 수 없습니다.",
                        "던전 d01 의 봉인 파일을 풀 수 없습니다. sealed.json 을 풀 수 없습니다: Error -3",
                        "던전 t02 를 읽을 수 없습니다. p1/problem.json 을 읽을 수 없습니다: 없음",
                        "이 문제의 채점 파일(tests.json)을 찾을 수 없습니다.", "이 문제의 채점 파일이 올바르지 않습니다. 기댓값이 없습니다",
                        "p1/extra.json 을 읽을 수 없습니다: Expecting value"):
            self.assertEqual(journey_text.error_text("open", message), ("문제 열기", refetch, message))
        self.assertEqual(journey_text.error_text("lang", "언어는 python 이나 javascript 여야 합니다: 'ruby'"),
                         ("언어 바꾸기", journey_text.NO_LANG, "언어는 python 이나 javascript 여야 합니다: 'ruby'"))

    def test_error_text_keeps_the_first_sentence_and_moves_the_rest(self):
        cases = (("open", "코드 파일을 읽을 수 없습니다: [Errno 13] 권한 없음", "코드 파일을 읽을 수 없습니다.", "[Errno 13] 권한 없음"),
                 ("run", "코드를 실행하지 못했습니다. 실행기 없음", "코드를 실행하지 못했습니다.", "실행기 없음"),
                 ("grade", "채점하지 못했습니다. 실행기 없음", "채점하지 못했습니다.", "실행기 없음"),
                 ("grade", "테스트 입력을 만들지 못했습니다. gen.py 오류", "테스트 입력을 만들지 못했습니다.", "gen.py 오류"),
                 ("save", "코드를 저장하지 못했습니다: 디스크가 가득 참", "코드를 저장하지 못했습니다.", "디스크가 가득 참"),
                 ("grade", "알고리즘 여행 기록을 저장하지 못했습니다. 기록은 바뀌지 않았으니 잠시 뒤 다시 해 주세요.\n[Errno 28] 자리 없음",
                  journey_text.NO_RECORD, "[Errno 28] 자리 없음"),
                 ("hint", "힌트를 모두 열었습니다.", "힌트를 모두 열었습니다.", ""),
                 ("open", "보스 문제는 중급 문제를 모두 통과하면 열립니다(1개 중 0개 통과).",
                  "보스 문제는 중급 문제를 모두 통과하면 열립니다(1개 중 0개 통과).", ""))
        for action, message, text, detail in cases:
            self.assertEqual(journey_text.error_text(action, message), (journey_text.ACTIONS[action], text, detail), message)
        self.assertEqual(journey_text.error_text("?", "힌트를 모두 열었습니다.")[0], "알림")

    def test_error_text_follows_the_service_messages(self):
        """서비스 문구가 바뀌어 규칙에서 빠지면 여기서 떨어짐."""
        service = self.service()
        for call in (lambda: service.problem("t01", "p9", "python"), lambda: service.problem("t02", "p1", "python"),
                     lambda: service.problem("t99", "p1", "python")):
            with self.assertRaises(JourneyError) as caught:
                call()
            self.assertEqual(journey_text.error_text("open", str(caught.exception))[1], journey_text.REFETCH, str(caught.exception))
        with self.assertRaises(JourneyError) as caught:
            check_lang("ruby")
        self.assertEqual(journey_text.error_text("lang", str(caught.exception))[1], journey_text.NO_LANG)


class WordsTest(SessionBase):
    def screen_texts(self):
        """이 모듈이 화면에 내는 글. 도움말과 자세히(원문)는 뺌."""
        service = self.service([grade_entry("t01/p1"), grade_entry("t01/p3", passed=False)])
        overview = service.overview()
        texts = [journey_text.ACTION, journey_text.map_count(overview), journey_text.bank_text(overview)[0]]
        for last in ("", "t03/p2"):
            item = journey_text.next_item(service, last, overview)
            texts += [item["title"], item["place"], item["role"], journey_text.track_line(overview, item)]
        info = service.dungeon("t01")
        texts += [journey_text.row_line(row, info) for row in info["problems"]] + [journey_text.dungeon_count(info)]
        names = [entry["title"] for entry in INDEX]
        for entry, following in zip(INDEX, names[1:] + [None]):
            texts += journey_text.dungeon_lines(entry, NUMBERS) + [journey_text.place(entry), journey_text.clear_text(entry["title"], following)]
            texts.append(journey_text.tier_tip(entry["boss_target"], True))
        heads = [journey_text.result_head(), journey_text.result_head(mine=2), journey_text.result_head(best=41.5),
                 journey_text.result_head("run", {"cases": [], "total": 2}, done=False),
                 journey_text.result_head("run", {"passed": 1, "total": 2}), journey_text.result_head("run", {"passed": 2, "total": 2}),
                 journey_text.result_head("run", {"fatal": {"line": 3}}), journey_text.result_head("run", {"cancelled": True}),
                 journey_text.result_head("grade", {}, done=False), journey_text.result_head("grade", {}, False, stage=grading.GEN_TEXT, seconds=3),
                 journey_text.result_head("grade", {"fatal": {"line": 2}}), journey_text.result_head("grade", {"cancelled": True}),
                 journey_text.result_head("grade", {"score": 100.0, "first_pass": True, "boss_opened": True,
                                                    "groups": [group("정확성", 70.0, 70.0), group("효율성", 30.0, 30.0)]})]
        for head in heads:
            texts += [head["title"], head["caption"]] + [part for banner in head["banners"] for part in banner[:2]]
        for message in ("문제 d01/p1 를 찾을 수 없습니다.", "언어는 python 이나 javascript 여야 합니다: 'x'", "코드를 저장하지 못했습니다: 오류",
                        "알고리즘 여행 기록을 저장하지 못했습니다. 기록은 바뀌지 않았으니 잠시 뒤 다시 해 주세요.\n오류"):
            texts += journey_text.error_text("open", message)[:2]
        return [text for text in texts if text]

    def test_no_exclamation_em_dash_or_inner_id(self):
        texts = self.screen_texts()
        self.assertGreater(len(texts), 80)
        for text in texts:
            self.assertNotIn("!", text)
            self.assertNotIn("—", text)
            self.assertIsNone(INNER_ID.search(text), text)


if __name__ == "__main__":
    unittest.main()
