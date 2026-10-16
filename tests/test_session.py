# -*- coding: utf-8 -*-
"""세션 서비스 테스트. 실제 문제 은행을 쓰고 풀이 폴더만 임시 폴더로 돌림.

실행: python -m unittest discover -s tests
"""
import argparse
import ast
import contextlib
import importlib.util
import io
import ntpath
import os
import random
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import adaptive  # noqa: E402
import session  # noqa: E402
import study  # noqa: E402


def right_answer(sess, view):
    """문항의 정답(퀴즈) 또는 모범 답안(코드)."""
    it = sess.cat[view["key"]]
    if it["kind"] == "quiz":
        q = it["q"]
        if q["type"] == "choice":
            return q["answer"] if len(q["answer"]) > 1 else q["answer"][0]
        return q["answer"] if q["type"] == "output" else q["answer"][0]
    return it["set"]["secrets"][it["spec"]["id"] + "/solution.py"]


def wrong_answer(view):
    if view["kind"] == "code":
        return "print('오답')\n"
    return 9 if view["type"] == "choice" else "틀린 답"


class SessionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="study_test_")
        self._saved = (study.SUBMISSIONS_DIR, study.USER_FILE, os.environ.pop("STUDY_USER", None))
        study.SUBMISSIONS_DIR = os.path.join(self.tmp, "submissions")
        study.USER_FILE = os.path.join(self.tmp, ".study_user")
        self.sess = session.Session("tester")

    def tearDown(self):
        study.SUBMISSIONS_DIR, study.USER_FILE, user = self._saved
        if user is not None:
            os.environ["STUDY_USER"] = user
        shutil.rmtree(self.tmp, ignore_errors=True)

    def answer_all(self, rid, correct=True, only=None):
        for view in self.sess.open_round(rid)["items"]:
            if only is not None and view["no"] not in only:
                continue
            self.sess.set_answer(rid, view["id"], right_answer(self.sess, view) if correct else wrong_answer(view))

    def first_real_round(self):
        """진단을 미응답으로 확정해 코드 문제가 섞인 1회차를 만듦."""
        rnd, _ = self.sess.ensure_round()
        result = self.sess.grade(rnd["id"], finalize=True)
        return result["next_round"]

    def make_round(self, rid, keys):
        """진단·회차는 무작위라 유형이 빠질 수 있어, 고른 문항으로 회차를 직접 만듦."""
        rnd = {"id": rid, "kind": "round", "focus": [], "items": keys, "retest": [], "shortages": [], "created": adaptive.now(),
               "tries": 0, "avg_level": 1}
        self.sess.prof["rounds"].append(rnd)
        adaptive.write_round("tester", rnd, self.sess.cat)
        adaptive.save_profile(self.sess.prof)

    # 사용자

    def test_save_and_load_user(self):
        self.assertIsNone(session.saved_user())
        session.save_user("abc-1_x")
        self.assertEqual(session.saved_user(), "abc-1_x")
        self.assertTrue(os.path.isdir(os.path.join(study.SUBMISSIONS_DIR, "abc-1_x")))
        for bad in ("", "한글", "a b", "../x", "-x"):
            with self.assertRaises(session.SessionError):
                session.save_user(bad)

    def test_id_follows_the_spelling_of_an_existing_folder(self):
        """다른 컴퓨터에서 대소문자만 다르게 넣은 ID 는 이미 있는 풀이 폴더 이름을 따름(철자가 다르면 제출이 올라가지 않음)."""
        os.makedirs(os.path.join(study.SUBMISSIONS_DIR, "Alice"))
        self.assertFalse(session.has_record("alice"))
        study.write_text(adaptive.profile_path("Alice"), '{"user": "Alice", "seed": 1, "rounds": [], "attempts": []}\n')
        self.assertTrue(session.has_record("alice"))
        self.assertEqual(session.save_user("alice"), "Alice")
        self.assertEqual(study.read_text(study.USER_FILE), "Alice\n")
        self.assertEqual(os.listdir(study.SUBMISSIONS_DIR), ["Alice"])
        study.write_text(study.USER_FILE, "ALICE\n")  # 고치기 전 버전이 저장해 둔 철자
        self.assertEqual(session.saved_user(), "Alice")
        self.assertEqual(session.save_user("bob"), "bob")

    # 회차 만들기

    def test_first_run_creates_diagnostic_once(self):
        rnd, created = self.sess.ensure_round()
        self.assertTrue(created)
        self.assertEqual((rnd["id"], rnd["kind"]), ("d1", "diag"))
        again, created = self.sess.ensure_round()
        self.assertFalse(created)
        self.assertEqual(again["id"], "d1")
        for name in ("README.md", "quiz.py"):
            self.assertTrue(os.path.isfile(os.path.join(self.sess.folder("d1"), name)))
        self.assertEqual(len(session.Session("tester").prof["rounds"]), 1)  # 디스크에 저장됨

    def test_round_view_has_everything_the_screen_needs(self):
        rid = self.first_real_round()
        view = self.sess.open_round(rid)
        self.assertEqual(view["kind"], "round")
        kinds = {it["kind"] for it in view["items"]}
        self.assertEqual(kinds, {"quiz", "code"})
        for it in view["items"]:
            self.assertTrue(it["body_md"].strip())
            self.assertFalse(it["answered"])
            self.assertIsNone(it["result"])
            if it["type"] == "choice":
                self.assertGreaterEqual(it["choices"], 4)
                self.assertIn("multi", it)
            if it["kind"] == "code":
                self.assertEqual(it["answer"], it["starter"])
        self.assertEqual([it["no"] for it in view["items"]], list(range(1, len(view["items"]) + 1)))

    # 답 저장

    def test_quiz_answers_round_trip_and_stay_cli_compatible(self):
        rnd, _ = self.sess.ensure_round()
        views = {v["type"]: v for v in self.sess.open_round("d1")["items"]}
        tricky = ['한 줄', "여러\n줄\n출력", 'He said "hi"', "작은'따옴표", "역슬래시 \\n 그대로", '"""삼중"""\n둘째 줄', "  앞뒤 공백 유지  x"]
        target = views.get("output") or views["short"]
        for text in tricky:
            self.sess.set_answer("d1", target["id"], text)
            parsed, error = study.parse_quiz_answers(os.path.join(self.sess.folder("d1"), "quiz.py"))
            self.assertIsNone(error, text)
            self.assertEqual(study.norm_out(str(parsed[target["id"]]), True), study.norm_out(text.strip() if target["type"] == "short" else text, True))
        choice = views["choice"]
        for value, stored in ((3, 3), ([2], 2), ([3, 1], [1, 3]), ([], None), (None, None)):
            self.sess.set_answer("d1", choice["id"], value)
            reopened = {v["id"]: v for v in self.sess.open_round("d1")["items"]}[choice["id"]]
            self.assertEqual(reopened["answer"], stored)
            self.assertEqual(reopened["answered"], stored is not None)
        # 다른 문항의 답이 지워지지 않음
        self.sess.set_answer("d1", target["id"], "남아 있어야 함")
        self.sess.set_answer("d1", choice["id"], 1)
        answers = {v["id"]: v["answer"] for v in self.sess.open_round("d1")["items"]}
        self.assertEqual((answers[target["id"]], answers[choice["id"]]), ("남아 있어야 함", 1))

    def test_literal_is_always_a_valid_python_literal(self):
        for value in (None, 3, [1, 3], "", "a", "a\nb", 'q"q', "t'''t", '"""\n', "back\\slash\nline", "끝이 따옴표\"\n둘째"):
            self.assertEqual(study.norm_out(str(ast.literal_eval(session.literal(value))), True) if isinstance(value, str) else ast.literal_eval(session.literal(value)),
                             study.norm_out(value, True) if isinstance(value, str) else value)

    def test_code_answer_saved_and_reset(self):
        rid = self.first_real_round()
        code = next(v for v in self.sess.open_round(rid)["items"] if v["kind"] == "code")
        self.sess.set_answer(rid, code["id"], "x = 1\r\nprint(x)")
        path = os.path.join(self.sess.folder(rid), code["id"] + ".py")
        self.assertEqual(study.read_text(path), "x = 1\nprint(x)\n")
        self.assertTrue({v["id"]: v for v in self.sess.open_round(rid)["items"]}[code["id"]]["answered"])
        self.assertEqual(self.sess.reset_item(rid, code["id"]), code["starter"])
        self.assertFalse({v["id"]: v for v in self.sess.open_round(rid)["items"]}[code["id"]]["answered"])
        self.assertEqual([f for f in os.listdir(self.sess.folder(rid)) if ".tmp" in f], [])  # 임시 파일이 남지 않음

    # 코드 실행

    def test_try_run_shows_examples_and_records_nothing(self):
        rid = self.first_real_round()
        before = len(self.sess.prof["attempts"])
        for code in (v for v in self.sess.open_round(rid)["items"] if v["kind"] == "code"):
            self.sess.set_answer(rid, code["id"], right_answer(self.sess, code))
            run = self.sess.try_run(rid, code["id"])
            self.assertEqual(run["message"], "", code["id"])
            self.assertEqual(run["ran"], run["examples"])
            self.assertEqual(run["examples"], self.sess.cat[code["key"]]["spec"]["examples"])
            self.assertTrue(all(c["ok"] and c["want"] and c["input"] for c in run["cases"]), (code["id"], run))
            self.sess.set_answer(rid, code["id"], "def solution(*a):\n    return None\n" if code["type"] == "return" else "print('x')\n")
            bad = self.sess.try_run(rid, code["id"])
            self.assertTrue(bad["message"] or any(not c["ok"] for c in bad["cases"]), code["id"])
        self.assertEqual(len(self.sess.prof["attempts"]), before)
        self.assertIsNone(adaptive.find_round(self.sess.prof, rid).get("results"))

    def test_sets_and_items_outside_exam_scope_are_left_out(self):
        """시험 범위 밖으로 표시한 세트(21차시)와 문항(20차시 캐스케이드 분류기 이후)은 단원과 회차에서 빠지고,
        그 문항이 든 예전 회차는 남은 문항만으로 열리고 채점됨."""
        self.assertEqual([u["id"] for u in adaptive.units()][-2:], ["s19", "s20"])
        cat = self.sess.cat
        self.assertFalse([k for k in cat if k.startswith("s21/")])
        self.assertNotIn("s20/Q17", cat)
        self.assertIn("s20/Q30", cat)
        for key, it in cat.items():
            self.assertTrue((it.get("q") or it.get("spec")).get("exam", True), key)
        keep = next(k for k in sorted(cat) if cat[k]["kind"] == "quiz")
        self.make_round("r91", [keep])
        rnd = adaptive.find_round(self.sess.prof, "r91")
        rnd["items"] += ["s20/Q17", "s21/p01"]  # 범위를 정하기 전에 만든 회차
        adaptive.save_profile(self.sess.prof)
        self.assertEqual([v["key"] for v in self.sess.open_round("r91")["items"]], [keep])
        result = self.sess.grade("r91", finalize=True)
        self.assertEqual([it["key"] for it in result["items"]], [keep])

    def test_try_run_reports_syntax_error_and_unfilled_blank(self):
        cat = self.sess.cat
        code = [k for k in sorted(cat) if cat[k]["kind"] == "code"]
        plain = next(k for k in code if cat[k]["type"] != "fill")
        fill = next(k for k in code if cat[k]["type"] == "fill")
        self.make_round("r90", [plain, fill])
        plain, fill = adaptive.fname_of(plain), adaptive.fname_of(fill)
        self.sess.set_answer("r90", plain, "def broken(:\n")
        self.assertIn("문법 오류", self.sess.try_run("r90", plain)["message"])
        self.sess.reset_item("r90", fill)
        self.assertIn("빈칸", self.sess.try_run("r90", fill)["message"])

    def test_try_run_reports_memory_overuse(self):
        rid = self.first_real_round()
        code = next(v for v in self.sess.open_round(rid)["items"] if v["kind"] == "code")
        self.sess.set_answer(rid, code["id"], "import time\ndata = b'x' * (200 * 1024 * 1024)\ntime.sleep(60)\n")
        # 회차 구성이 무작위라 빈칸 채우기 문제가 뽑혀도 실행까지 가도록 빈칸 검사를 건너뜀
        with mock.patch.object(study, "MEMORY_LIMIT_MB", 128), mock.patch.object(study, "check_fill", return_value=None):
            self.assertIn("메모리 초과", self.sess.try_run(rid, code["id"])["message"])

    # 채점 · 기록

    def test_untouched_round_is_not_recorded(self):
        self.sess.ensure_round()
        result = self.sess.grade("d1")
        self.assertTrue(result["untouched"])
        self.assertEqual(self.sess.prof["attempts"], [])
        self.assertFalse(result["completed"])

    def test_partial_submit_records_only_answered_items(self):
        self.sess.ensure_round()
        self.answer_all("d1", only={1, 2, 3})
        result = self.sess.grade("d1")
        self.assertEqual(len(self.sess.prof["attempts"]), 3)
        self.assertFalse(result["completed"])
        self.assertEqual(result["unanswered"], result["round"]["size"] - 3)
        self.assertIsNone(result["next_round"])
        self.answer_all("d1")  # 나머지를 마저 풀면 그때가 그 문항들의 첫 시도
        result = self.sess.grade("d1")
        self.assertTrue(result["completed_now"])
        self.assertEqual(result["next_round"], "r01")
        firsts = adaptive.first_attempts(self.sess.prof)
        self.assertEqual(len(firsts), result["round"]["size"])
        self.assertTrue(all(a["ok"] for a in firsts))

    def test_finalize_marks_blanks_wrong_and_moves_on(self):
        self.sess.ensure_round()
        self.answer_all("d1", only={1})
        result = self.sess.grade("d1", finalize=True)
        self.assertTrue(result["completed_now"])
        self.assertEqual(result["next_round"], "r01")
        size = result["round"]["size"]
        self.assertEqual(len(self.sess.prof["attempts"]), size)
        self.assertEqual(sum(1 for a in self.sess.prof["attempts"] if a.get("skipped")), size - 1)
        self.assertEqual(sum(1 for a in self.sess.prof["attempts"] if a["ok"]), 1)
        again = self.sess.grade("d1", finalize=True)  # 다시 채점해도 중복 기록 없음
        self.assertEqual(len(self.sess.prof["attempts"]), size)
        self.assertFalse(again["completed_now"])
        self.assertIsNone(again["next_round"])

    def test_first_attempt_is_what_counts_for_mastery(self):
        rid = self.first_real_round()
        self.answer_all(rid, correct=False)
        result = self.sess.grade(rid, finalize=True)
        self.assertEqual(result["earned"], 0)
        size = result["round"]["size"]
        self.answer_all(rid, correct=True)  # 고쳐서 다시 채점 = 연습
        result = self.sess.grade(rid)
        self.assertEqual(result["earned"], result["total"])
        in_round = [a for a in self.sess.prof["attempts"] if a["round"] == rid]
        self.assertEqual(sum(1 for a in in_round if a["try"] == 1 and not a["ok"]), size)
        self.assertEqual(sum(1 for a in in_round if a["try"] == 2 and a["ok"]), size)
        self.assertEqual(len(adaptive.first_attempts(self.sess.prof)), len(self.sess.prof["attempts"]) - size)

    def test_all_correct_round_scores_full_and_gui_files_match_ci_grading(self):
        rid = self.first_real_round()
        self.answer_all(rid)
        result = self.sess.grade(rid, finalize=True)
        self.assertEqual((result["earned"], result["ratio"]), (result["total"], 1.0))
        self.assertTrue(result["verdicts"])
        self.assertTrue(all(it["state"] == "ok" for it in result["items"]))
        # CI 가 쓰는 경로(파일만 보고 채점)로도 같은 결과
        fresh = session.Session("tester")
        rnd = adaptive.find_round(fresh.prof, rid)
        self.assertTrue(all(it["state"] == "ok" for it in adaptive.grade_round("tester", rnd, fresh.cat)))
        self.assertEqual(fresh.prof["rounds"][-1]["id"], result["next_round"])

    # 배점

    def first_code(self):
        return next(k for k in sorted(self.sess.cat, key=study.natural_key) if self.sess.cat[k]["kind"] == "code")

    def test_round_is_out_of_100_and_each_item_earns_its_round_points(self):
        """회차를 다 맞히면 100점이고, 일부만 맞히면 맞힌 문항의 회차 배점을 더한 점수임. 기록된 점수도 같음."""
        keys = self.quiz_keys("s03", 3) + [self.first_code()]
        points = adaptive.round_points(keys, self.sess.cat)
        result = self.submit("r91", right=keys)
        self.assertEqual((result["earned"], result["total"], result["round"]["score"]), (100, 100, "100/100"))
        self.assertEqual({it["key"]: it["points"] for it in result["items"]}, points)
        self.assertEqual(adaptive.find_round(self.sess.prof, "r91")["score"], "100/100")
        right, wrong = [keys[0], keys[3]], [keys[1], keys[2]]
        result = self.submit("r92", right=right, wrong=wrong)
        earned = points[keys[0]] + points[keys[3]]
        self.assertEqual((result["earned"], result["total"]), (earned, 100))
        self.assertEqual({it["key"]: it["earned"] for it in result["items"]}, {k: points[k] if k in right else 0 for k in keys})
        self.assertEqual(adaptive.find_round(self.sess.prof, "r92")["score"], "%d/100" % earned)
        self.assertEqual({v["key"]: v["points"] for v in self.sess.open_round("r92")["items"]}, points)

    def test_rounds_saved_with_old_points_are_shown_out_of_100(self):
        """예전 배점("6/12")으로 저장된 회차도 화면에 주는 점수는 지금 배점으로 다시 셈.
        지금 점수는 문항별 마지막 결과로, 첫 제출 점수는 그 회차의 첫 시도 기록으로 셈."""
        k1, k2, k3 = self.quiz_keys("s02", 3)
        code = self.first_code()
        points = adaptive.round_points([k1, code, k2, k3], self.sess.cat)  # submit 이 회차에 넣는 순서
        first = points[k1] + points[code]
        self.submit("r91", right=[k1, code], wrong=[k2], blank=[k3])
        rnd = adaptive.find_round(self.sess.prof, "r91")
        self.assertEqual((rnd["score"], rnd["first_score"]), ("%d/100" % first,) * 2)
        self.assertEqual(adaptive.last_ratio(self.sess.prof), first / 100)  # 다음 회차 크기를 정하는 비율도 화면 점수와 같음
        rnd.update(score="6/12", first_score="6/12")
        adaptive.save_profile(self.sess.prof)
        summary = next(r for r in session.Session("tester").rounds() if r["id"] == "r91")
        self.assertEqual((summary["score"], summary["first_score"]), ("%d/100" % first,) * 2)
        view = next(v for v in self.sess.open_round("r91")["items"] if v["key"] == k2)
        self.sess.set_answer("r91", view["id"], right_answer(self.sess, view))
        result = self.sess.grade("r91")  # 고쳐서 다시 채점하면 지금 점수만 오름
        self.assertEqual((result["round"]["score"], result["round"]["first_score"]), ("%d/100" % (first + points[k2]), "%d/100" % first))

    def test_first_score_kept_for_next_round_size_is_the_first_try_score(self):
        """나눠 채점하다 이미 채점한 답을 고친 뒤 회차를 끝내도, 저장하는 첫 제출 점수는 첫 시도 기록으로 센 화면의 점수와 같음."""
        k1, k2, k3 = self.quiz_keys("s02", 3)
        points = adaptive.round_points([k1, k2, k3], self.sess.cat)
        self.make_round("r91", [k1, k2, k3])
        views = {v["key"]: v for v in self.sess.open_round("r91")["items"]}
        self.sess.set_answer("r91", views[k1]["id"], wrong_answer(views[k1]))
        self.sess.grade("r91")  # k1 만 채점해 첫 시도가 오답으로 남음
        for key in (k1, k2, k3):
            self.sess.set_answer("r91", views[key]["id"], right_answer(self.sess, views[key]))
        result = self.sess.grade("r91")
        first = points[k2] + points[k3]
        self.assertTrue(result["completed_now"])
        self.assertEqual((result["round"]["score"], result["round"]["first_score"]), ("100/100", "%d/100" % first))
        self.assertEqual(adaptive.find_round(self.sess.prof, "r91")["first_score"], "%d/100" % first)
        self.assertEqual(adaptive.last_ratio(self.sess.prof), first / 100)

    def test_unfinished_round_readme_is_rewritten_with_round_points(self):
        """배점을 바꾸기 전에 만든 회차도 이어 풀 때 문제지(README.md)를 지금 배점으로 다시 씀. 답안지와 코드 파일은 그대로 둠.
        문제지를 쓰지 못해도 이어 풀 수 있음."""
        rnd, _ = self.sess.ensure_round()
        folder = self.sess.folder(rnd["id"])
        for view in self.sess.open_round(rnd["id"])["items"][:2]:
            self.sess.set_answer(rnd["id"], view["id"], wrong_answer(view))
        readme = os.path.join(folder, "README.md")
        fresh = study.read_text(readme)
        others = {name: study.read_text(os.path.join(folder, name)) for name in os.listdir(folder) if name != "README.md"}
        study.write_text(readme, "# 옛 배점이 적힌 문제지\n")
        again, created = self.sess.ensure_round()
        self.assertEqual((again["id"], created), (rnd["id"], False))
        self.assertEqual(study.read_text(readme), fresh)
        self.assertEqual({name: study.read_text(os.path.join(folder, name)) for name in os.listdir(folder) if name != "README.md"}, others)
        with mock.patch.object(adaptive, "write_round", side_effect=PermissionError("locked")):
            self.assertEqual(self.sess.ensure_round()[0]["id"], rnd["id"])

    def test_answer_sheet_and_round_readme_show_round_points(self):
        keys = self.quiz_keys("s03", 2) + [self.first_code()]
        points = adaptive.round_points(keys, self.sess.cat)
        self.make_round("r91", keys)
        folder = self.sess.folder("r91")

        def sheet():
            lines = study.read_text(os.path.join(folder, "quiz.py")).split("\n")
            return {line.split(" = ")[0]: line.rsplit(" · ", 1)[1] for line in lines if " = " in line}

        want = {adaptive.fname_of(k): "%d점" % points[k] for k in keys[:2]}
        self.assertEqual(sheet(), want)
        readme = study.read_text(os.path.join(folder, "README.md"))
        for key in keys:
            self.assertRegex(readme, r"(?m)^## %s \(.* · %d점\)$" % (adaptive.fname_of(key), points[key]))
        view = self.sess.open_round("r91")["items"][0]
        self.sess.set_answer("r91", view["id"], wrong_answer(view))  # 화면에서 답을 저장해 답안지를 다시 써도 같은 점수가 남음
        self.assertEqual(sheet(), want)

    def test_items_carry_their_reference_list(self):
        """은행 문항의 ref(참고 자료)가 문항 모양에 들어감. 없으면 빈 목록."""
        k1, k2 = self.quiz_keys("s03", 2)
        code = self.first_code()
        self.make_round("r91", [k1, k2, code])
        cat = self.sess.cat
        with mock.patch.dict(cat[k1]["q"], ref=["강의 3차시 12쪽", "과제 3차시 3번"]), mock.patch.dict(cat[code]["spec"], ref=["4주차 요약본 1.2"]), \
                mock.patch.dict(cat[k2]["q"]):
            cat[k2]["q"].pop("ref", None)  # 은행 문항에는 ref 가 있어서 없는 경우는 여기서 지움. patch.dict 가 끝나면 되돌림
            views = {v["key"]: v["ref"] for v in self.sess.open_round("r91")["items"]}
        self.assertEqual(views, {k1: ["강의 3차시 12쪽", "과제 3차시 3번"], k2: [], code: ["4주차 요약본 1.2"]})

    # 해설

    def test_explain_is_locked_until_graded(self):
        self.sess.ensure_round()
        first = self.sess.open_round("d1")["items"][0]
        with self.assertRaises(session.SessionError):
            self.sess.explain("d1", first["id"])
        self.answer_all("d1", only={1})
        self.sess.grade("d1")  # 일부만 채점한 상태에서는 그 문항 해설도 잠겨 있음
        with self.assertRaises(session.SessionError):
            self.sess.explain("d1", first["id"])
        self.sess.grade("d1", finalize=True)
        info = self.sess.explain("d1", first["id"])
        self.assertTrue(info["answer"] and info["explain"])
        self.assertFalse(info["markdown"])
        rid = self.sess.latest()["id"]
        code = next(v for v in self.sess.open_round(rid)["items"] if v["kind"] == "code")
        with self.assertRaises(session.SessionError):
            self.sess.explain(rid, code["id"])
        self.sess.grade(rid, finalize=True)
        info = self.sess.explain(rid, code["id"])
        self.assertTrue(info["solution"] and info["markdown"])

    def test_terminal_go_asks_first_and_explain_stays_locked(self):
        """화면에서 풀다 만 회차를 터미널 go 가 묻지 않고 채점하지 않고, 풀고 있는 회차의 해설도 열지 않음."""
        session.save_user("tester")
        self.sess.ensure_round()
        self.answer_all("d1", only={1})
        first = self.sess.open_round("d1")["items"][0]
        out = io.StringIO()
        with mock.patch("builtins.input", return_value=""), contextlib.redirect_stdout(out):
            study.cmd_go(argparse.Namespace())
        self.assertEqual(adaptive.load_profile("tester")["attempts"], [])
        self.assertIn("채점하지 않았습니다", out.getvalue())
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            study.cmd_explain(argparse.Namespace(set=first["id"], item=None))
        with mock.patch("builtins.input", return_value="y"), contextlib.redirect_stdout(out):
            study.cmd_go(argparse.Namespace())
        self.assertEqual(len(adaptive.load_profile("tester")["attempts"]), 1)
        self.assertNotIn("explain", out.getvalue())  # 회차가 끝나기 전에는 해설 명령을 권하지 않음

    def test_explain_by_round_item_id_leaves_out_bank_points(self):
        """회차 배점은 은행 배점과 달라서 회차 문항 ID(s03_Q1)로 해설을 보면 점수를 적지 않음. 세트 방식(s03 Q1)은 은행 배점을 적음."""
        key = self.quiz_keys("s03", 1)[0]
        q = self.sess.cat[key]["q"]
        heads = []
        for args in (argparse.Namespace(set=adaptive.fname_of(key), item=None), argparse.Namespace(set="s03", item=q["id"])):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                study.cmd_explain(args)
            heads.append(out.getvalue().split("\n")[0])
        label = "[s03 %s] %s" % (q["id"], study.QTYPE_LABEL[q["type"]])
        self.assertEqual(heads, [label, "%s · %d점" % (label, q["points"])])

    def test_unquoted_text_answer_is_explained(self):
        """터미널 방식으로 quiz.py 에 따옴표 없이 글자를 적으면 오답 사유에 적는 법이 나옴."""
        rnd, _ = self.sess.ensure_round()
        view = next(v for v in self.sess.open_round("d1")["items"] if v["kind"] == "quiz")
        path = os.path.join(self.sess.folder("d1"), "quiz.py")
        lines = [view["id"] + " = abc" if line.startswith(view["id"] + " = ") else line for line in study.read_text(path).split("\n")]
        study.write_text(path, "\n".join(lines))
        graded = next(it for it in adaptive.grade_round("tester", rnd, self.sess.cat) if it["id"] == view["id"])
        self.assertEqual(graded["state"], "wrong")
        self.assertIn("따옴표", graded["detail"])

    # 오답 노트

    def quiz_keys(self, unit, count):
        cat = self.sess.cat
        return [k for k in sorted(cat, key=study.natural_key) if cat[k]["unit"] == unit and cat[k]["kind"] == "quiz"][:count]

    def submit(self, rid, right=(), wrong=(), blank=()):
        """고른 문항으로 회차를 만들어 right 는 정답, wrong 은 오답을 적고 blank 는 비운 채 제출함."""
        self.make_round(rid, list(right) + list(wrong) + list(blank))
        for view in self.sess.open_round(rid)["items"]:
            if view["key"] in right or view["key"] in wrong:
                self.sess.set_answer(rid, view["id"], right_answer(self.sess, view) if view["key"] in right else wrong_answer(view))
        return self.sess.grade(rid, finalize=True)

    def test_wrong_notes_hold_first_attempt_misses_by_unit(self):
        """첫 시도에 틀렸거나 비워 둔 문항만 단원별로 모임. 단원은 차시 순이고, 단원 안에서는 최근에 틀린 것이 위, 같이 채점한 문항은 문제지 순서."""
        self.assertEqual(self.sess.wrong_notes(), [])
        a1, a2, a3, a4 = self.quiz_keys("s02", 4)
        b1, c1 = self.quiz_keys("s05", 1)[0], self.quiz_keys("s07", 1)[0]
        self.submit("r91", right=[a1], wrong=[a2, a3, c1], blank=[b1])
        self.submit("r92", wrong=[a4])
        notes = self.sess.wrong_notes()
        self.assertEqual([(u["unit"], u["title"]) for u in notes], [(u, adaptive.cat_unit_title(self.sess.cat, u)) for u in ("s02", "s05", "s07")])
        self.assertEqual([[n["key"] for n in u["items"]] for u in notes], [[a4, a2, a3], [b1], [c1]])
        it = self.sess.cat[b1]
        self.assertEqual(notes[1]["items"][0], {
            "key": b1, "id": adaptive.fname_of(b1), "type_label": study.QTYPE_LABEL[it["type"]], "level": it["level"],
            "points": adaptive.round_points([a1, a2, a3, c1, b1], self.sess.cat)[b1],
            "round": "r91", "round_title": "91회차 미니 모의고사", "completed": True, "at": notes[1]["items"][0]["at"], "skipped": True,
            "wrong_count": 1, "fixed": False})
        self.assertEqual([(n["round"], n["skipped"]) for n in notes[0]["items"]], [("r92", False), ("r91", False), ("r91", False)])

    def test_wrong_notes_mark_items_answered_right_later(self):
        """다른 회차의 첫 시도나 같은 회차의 다시 채점에서 맞히면 fixed. 그 뒤에 또 틀리면 그 회차가 마지막으로 틀린 회차가 됨.
        그보다 앞 회차를 다시 채점해 맞힌 것은 fixed 가 아님."""
        k1, k2 = self.quiz_keys("s03", 2)
        self.submit("r91", wrong=[k1, k2])
        self.submit("r92", right=[k1])
        view = next(v for v in self.sess.open_round("r91")["items"] if v["key"] == k2)
        self.sess.set_answer("r91", view["id"], right_answer(self.sess, view))
        self.sess.grade("r91")
        notes = {n["key"]: n for n in self.sess.wrong_notes()[0]["items"]}
        self.assertEqual([(notes[k]["round"], notes[k]["wrong_count"], notes[k]["fixed"]) for k in (k1, k2)], [("r91", 1, True), ("r91", 1, True)])
        self.submit("r93", wrong=[k1])
        notes = self.sess.wrong_notes()[0]["items"]
        self.assertEqual([(n["key"], n["round"], n["wrong_count"], n["fixed"]) for n in notes], [(k1, "r93", 2, False), (k2, "r91", 1, True)])
        view = next(v for v in self.sess.open_round("r91")["items"] if v["key"] == k1)
        self.sess.set_answer("r91", view["id"], right_answer(self.sess, view))
        self.sess.grade("r91")
        notes = self.sess.wrong_notes()[0]["items"]
        self.assertEqual([(n["key"], n["round"], n["wrong_count"], n["fixed"]) for n in notes], [(k1, "r93", 2, False), (k2, "r91", 1, True)])

    def test_wrong_notes_skip_items_outside_exam_scope(self):
        keep = self.quiz_keys("s04", 1)[0]
        self.submit("r91", wrong=[keep])
        for key in ("s20/Q17", "s21/p01"):  # 시험 범위를 정하기 전에 남은 기록
            self.sess.prof["attempts"].append({"round": "r91", "item": key, "try": 1, "ok": False, "at": adaptive.now()})
        self.assertEqual([n["key"] for u in self.sess.wrong_notes() for n in u["items"]], [keep])

    def test_wrong_item_shows_the_answer_written_in_that_round(self):
        key = next(k for k in sorted(self.sess.cat, key=study.natural_key) if self.sess.cat[k]["type"] == "short")
        name = adaptive.fname_of(key)
        for rid, answer in (("r91", "첫 번째 오답"), ("r92", "두 번째 오답")):
            self.make_round(rid, [key])
            self.sess.set_answer(rid, name, answer)
            self.sess.grade(rid, finalize=True)
        self.assertEqual(self.sess.wrong_notes()[0]["items"][0]["round"], "r92")
        for rid, answer in (("r91", "첫 번째 오답"), ("r92", "두 번째 오답")):
            item = self.sess.wrong_item(rid, name)
            self.assertEqual((item["key"], item["answer"], item["no"]), (key, answer, 1))
            self.assertTrue(item["body_md"].strip())
        self.assertTrue(self.sess.explain("r92", name)["answer"])
        study.write_text(os.path.join(self.sess.folder("r91"), "quiz.py"), "%s = '깨진\n" % name)
        with self.assertRaises(session.SessionError):
            self.sess.wrong_item("r91", name)

    # 현황

    def test_overview_tracks_progress(self):
        before = self.sess.overview()
        self.assertEqual((before["readiness"], before["current"], before["rounds"]), (0, None, []))
        self.sess.ensure_round()
        self.answer_all("d1")
        self.sess.grade("d1")
        after = self.sess.overview()
        self.assertGreater(after["readiness"], 0)
        self.assertEqual(after["current"]["id"], "r01")
        self.assertEqual(len(after["units"]), len(adaptive.units()))
        self.assertTrue(all(u["tested"] for u in after["units"]))
        self.assertEqual([r["id"] for r in after["rounds"]], ["d1", "r01"])

    def other_member(self, user, correct):
        """다른 사람의 풀이 기록을 만듦. 진단에서 앞의 correct 문항만 맞히고 제출함."""
        sess = session.Session(user)
        sess.ensure_round()
        for view in sess.open_round("d1")["items"][:correct]:
            sess.set_answer("d1", view["id"], right_answer(sess, view))
        sess.grade("d1", finalize=True)

    def test_team_summarizes_every_readable_record_in_readiness_order(self):
        self.other_member("tester", 30)
        self.other_member("other", 3)
        self.sess = session.Session("tester")
        os.makedirs(os.path.join(study.SUBMISSIONS_DIR, "nobody"))  # 풀이 기록이 없는 폴더
        study.write_text(adaptive.profile_path("broken"), '{"rounds": [<<<<<<<')
        study.write_text(adaptive.profile_path("odd"), '{"rounds": 3, "attempts": [1], "seed": 1}')
        study.write_text(adaptive.profile_path("list"), "[]")
        rows = self.sess.team()
        self.assertEqual([(row["user"], row["me"]) for row in rows], [("tester", True), ("other", False)])
        self.assertGreater(rows[0]["readiness"], rows[1]["readiness"])
        for row in rows:
            prof = adaptive.load_profile(row["user"])
            states = adaptive.all_states(prof, self.sess.cat)
            firsts = adaptive.first_attempts(prof)
            self.assertEqual(row["readiness"], adaptive.readiness(states))
            self.assertEqual((row["mastered"], row["total"]), (sum(1 for st in states if st["mastered"]), len(states)))
            self.assertEqual((row["rounds"], row["attempts"]), (len(prof["rounds"]), len(firsts)))
            self.assertAlmostEqual(row["accuracy"], sum(1 for a in firsts if a["ok"]) / len(firsts))
            self.assertEqual(row["last"], max(a["at"] for a in prof["attempts"])[:10])
            self.assertEqual([unit["unit"] for unit in row["units"]], [s["id"] for s in adaptive.units()])
            self.assertTrue(set(row["weak"]) | set(row["strong"]) <= {unit["unit"] for unit in row["units"]})
        mine = self.sess.overview()
        self.assertEqual((rows[0]["readiness"], rows[0]["mastered"], rows[0]["units"]), (mine["readiness"], mine["mastered"], mine["units"]))

    def test_dashboard_draws_from_the_same_summary_as_the_team_screen(self):
        self.other_member("tester", 20)
        spec = importlib.util.spec_from_file_location("dashboard", os.path.join(study.ROOT, "tools", "dashboard.py"))
        dashboard = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(dashboard)
        out = os.path.join(self.tmp, "out")
        with mock.patch.object(sys, "argv", ["dashboard.py", "--out", out]), contextlib.redirect_stdout(io.StringIO()):
            dashboard.main()
        row = session.Session("tester").team()[0]
        self.assertIn("| tester | %s %d%% | %d/%d |" % (dashboard.bar(row["readiness"] / 100), row["readiness"], row["mastered"], row["total"]),
                      study.read_text(os.path.join(out, "DASHBOARD.md")))
        self.assertIn("준비도 %d%% · 숙달 %d/%d · 회차 %d" % (row["readiness"], row["mastered"], row["total"], row["rounds"]),
                      study.read_text(os.path.join(out, "dashboard.svg")))

    def test_path_on_another_drive_is_shown_in_full(self):
        """Windows 에서 임시 폴더(C:)와 저장소(D:)처럼 드라이브가 다르면 상대 경로를 만들 수 없음. 안내를 찍다가 멈추지 않고 절대 경로를 보여 줌."""
        with mock.patch.object(os, "path", ntpath), mock.patch.object(study, "ROOT", "D:\\repo"):
            self.assertEqual(study.shown_path("D:\\repo\\submissions\\tester\\d1"), "submissions\\tester\\d1")
            self.assertEqual(study.shown_path("C:\\Temp\\out"), "C:\\Temp\\out")

    # 기록을 망가뜨리던 경로들

    def test_broken_answer_sheet_is_never_treated_as_empty(self):
        self.sess.ensure_round()
        views = self.sess.open_round("d1")["items"]
        for view in [v for v in views if v["type"] == "choice"][:4]:
            self.sess.set_answer("d1", view["id"], 1)
        path = os.path.join(self.sess.folder("d1"), "quiz.py")
        good = study.read_text(path)
        one_bad_line = good.replace(" = 1 ", " = 1번 ", 1)
        for broken in (one_bad_line, "<<<<<<< HEAD\n" + good + "=======\n>>>>>>> main\n", good + 'x = """끝나지 않은 문자열\n'):
            study.write_text(path, broken)
            self.assertTrue(self.sess.quiz_problem("d1"))
            for call in (lambda: self.sess.open_round("d1"), lambda: self.sess.set_answer("d1", views[5]["id"], 1),
                         lambda: self.sess.grade("d1"), lambda: self.sess.grade("d1", finalize=True)):
                with self.assertRaises(session.SessionError):
                    call()
            self.assertEqual(study.read_text(path), broken)  # 파일을 건드리지 않음
            self.assertEqual(self.sess.prof["attempts"], [])  # 아무것도 기록하지 않음
        study.write_text(path, one_bad_line)
        kept = self.sess.repair_quiz("d1")
        self.assertEqual(kept, 3)  # 깨진 한 줄만 잃음
        self.assertTrue(os.path.isfile(path + ".bak"))
        self.assertIsNone(self.sess.quiz_problem("d1"))
        self.assertEqual(sum(1 for v in self.sess.open_round("d1")["items"] if v["answered"]), 3)

    def test_repair_keeps_multiline_and_hash_answers(self):
        """답안지 복구가 프로그램이 쓴 형식 그대로인 여러 줄 답과 # 이 든 답을 버리지 않음."""
        self.sess.ensure_round()
        views = [v for v in self.sess.open_round("d1")["items"] if v["type"] in ("output", "short")][:3]
        values = ["1\n2\n3", "# 주석", "a = 1  # 한 줄"]
        for view, value in zip(views, values):
            self.sess.set_answer("d1", view["id"], value)
        path = os.path.join(self.sess.folder("d1"), "quiz.py")
        study.write_text(path, study.read_text(path) + "x = (\n")
        self.assertEqual(self.sess.repair_quiz("d1"), 3)
        answers = {v["id"]: v["answer"] for v in self.sess.open_round("d1")["items"]}
        self.assertEqual([answers[view["id"]] for view in views], values)

    def test_number_written_by_hand_opens_as_text(self):
        """터미널 방식으로 따옴표 없이 적은 숫자 답(Q14 = 3)을 화면용으로 열면 글자로 돌려줌."""
        self.sess.ensure_round()
        view = next(v for v in self.sess.open_round("d1")["items"] if v["type"] in ("output", "short"))
        path = os.path.join(self.sess.folder("d1"), "quiz.py")
        study.write_text(path, study.read_text(path).replace("%s = None" % view["id"], "%s = 3" % view["id"]))
        opened = next(v for v in self.sess.open_round("d1")["items"] if v["id"] == view["id"])
        self.assertEqual((opened["answer"], opened["answered"]), ("3", True))

    def test_failed_save_does_not_leave_the_round_looking_submitted(self):
        """회차 제출 중 profile.json 저장이 실패하면 메모리의 채점 결과를 버림. 남겨 두면 해설이 열리고 다시 채점이 첫 제출로 기록됨."""
        self.sess.ensure_round()
        first = self.sess.open_round("d1")["items"][0]
        self.sess.set_answer("d1", first["id"], wrong_answer(first))
        with mock.patch.object(adaptive, "save_profile", side_effect=PermissionError(13, "잠김")):
            with self.assertRaises(session.SessionError):
                self.sess.grade("d1", finalize=True)
        self.assertEqual(self.sess.overview()["current"]["id"], "d1")
        self.assertEqual(self.sess.prof["attempts"], [])
        with self.assertRaises(session.SessionError):
            self.sess.explain("d1", first["id"])
        self.assertTrue(self.sess.grade("d1", finalize=True)["completed_now"])  # 다시 누르면 그대로 제출됨
        firsts = [a for a in adaptive.load_profile("tester")["attempts"] if a["item"] == first["key"]]
        self.assertEqual([(a["try"], a["ok"]) for a in firsts], [(1, False)])

    def test_unsafe_characters_never_reach_the_files(self):
        cat = self.sess.cat  # 회차는 무작위라 글로 답하는 문항이 없을 때가 있어서, 고른 문항으로 직접 만듦
        keys = [next(k for k in sorted(cat) if cat[k]["kind"] == "quiz" and cat[k]["type"] == "short"),
                next(k for k in sorted(cat) if cat[k]["kind"] == "code")]
        rid = "r90"
        rnd = {"id": rid, "kind": "round", "focus": [], "items": keys, "retest": [], "shortages": [], "created": adaptive.now(),
               "tries": 0, "avg_level": 1}
        self.sess.prof["rounds"].append(rnd)
        adaptive.write_round("tester", rnd, cat)
        adaptive.save_profile(self.sess.prof)
        views = self.sess.open_round(rid)["items"]
        text_item = next(v for v in views if v["type"] in ("output", "short"))
        code = next(v for v in views if v["kind"] == "code")
        self.sess.set_answer(rid, text_item["id"], "a\x00b\ud83dc\r\nd")
        self.sess.set_answer(rid, code["id"], "x = 1\x00\ud800\n")
        reopened = {v["id"]: v for v in self.sess.open_round(rid)["items"]}
        self.assertEqual(reopened[text_item["id"]]["answer"].replace("\n", " "), "abc d")
        self.assertEqual(reopened[code["id"]]["answer"], "x = 1\n")

    def test_regrading_does_not_change_the_score_used_for_next_round_size(self):
        rid = self.first_real_round()
        self.answer_all(rid, correct=False)
        self.sess.grade(rid, finalize=True)
        rnd = adaptive.find_round(self.sess.prof, rid)
        first, ratio = rnd["first_score"], adaptive.last_ratio(self.sess.prof)
        self.assertEqual(ratio, 0.0)
        self.answer_all(rid, correct=True)
        result = self.sess.grade(rid)
        self.assertEqual(result["earned"], result["total"])
        rnd = adaptive.find_round(self.sess.prof, rid)
        self.assertEqual(rnd["first_score"], first)
        self.assertNotEqual(rnd["score"], first)
        ordered = [r for r in self.sess.prof["rounds"] if r.get("completed_at")]
        self.assertEqual(ordered[-1]["id"], rid)
        self.assertEqual(adaptive.last_ratio(self.sess.prof), 0.0)

    def test_two_sessions_do_not_overwrite_each_others_first_attempts(self):
        self.sess.ensure_round()
        other = session.Session("tester")  # 다른 창(또는 터미널)
        first = self.sess.open_round("d1")["items"][0]
        other.set_answer("d1", first["id"], wrong_answer(first))
        other.grade("d1")  # 오답이 첫 시도로 기록됨
        self.sess.set_answer("d1", first["id"], right_answer(self.sess, first))
        self.sess.grade("d1")  # 앞서 열어 둔 세션이 고쳐서 채점
        attempts = [a for a in session.Session("tester").prof["attempts"] if a["item"] == first["key"]]
        self.assertEqual([(a["try"], a["ok"]) for a in attempts], [(1, False), (2, True)])

    def test_renamed_folder_keeps_the_record_in_one_place(self):
        """ID 를 고치려고 풀이 폴더 이름을 바꾼 뒤에도 기록이 옛 ID 폴더로 갈라지지 않음."""
        self.sess.ensure_round()
        os.rename(os.path.join(study.SUBMISSIONS_DIR, "tester"), os.path.join(study.SUBMISSIONS_DIR, "fixed"))
        result = session.Session("fixed").grade("d1", finalize=True)
        self.assertTrue(result["completed_now"])
        self.assertFalse(os.path.exists(os.path.join(study.SUBMISSIONS_DIR, "tester")))
        prof = session.Session("fixed").prof
        self.assertEqual(prof["user"], "fixed")
        self.assertEqual([r["id"] for r in prof["rounds"]], ["d1", "r01"])

    def test_corrupt_profile_raises_readable_error(self):
        self.sess.ensure_round()
        study.write_text(adaptive.profile_path("tester"), '{"user": "tester", "rounds": [<<<<<<<')
        with self.assertRaises(session.SessionError):
            session.Session("tester")
        with self.assertRaises(session.SessionError):
            self.sess.grade("d1", finalize=True)

    def test_choice_buttons_match_the_real_options_for_every_question(self):
        for key, it in self.sess.cat.items():
            if it["kind"] == "quiz" and it["type"] == "choice":
                count = session.choice_count(adaptive.quiz_section(it["set"], it["q"]["id"]))
                self.assertGreaterEqual(count, max(it["q"]["answer"]), key)
                self.assertIn(count, (4, 5), key)
        for key in ("s09/Q3", "s10/Q2", "s04/Q5"):  # 보기가 코드 블록인 문항
            it = self.sess.cat[key]
            self.assertEqual(session.choice_count(adaptive.quiz_section(it["set"], it["q"]["id"])), 4, key)

    def test_choice_body_splits_into_question_and_options_for_every_question(self):
        """보기 카드에 쓰는 나누기가 보기 수 세기와 어긋나지 않고, 지문과 보기가 비지 않음."""
        for key, it in self.sess.cat.items():
            if it["kind"] == "quiz" and it["type"] == "choice":
                body = adaptive.quiz_section(it["set"], it["q"]["id"])
                stem, options = session.split_choices(body)
                self.assertEqual(len(options), session.choice_count(body), key)
                self.assertTrue(any(block.get("text", "").strip() for block in stem), key)
                for option in options:
                    self.assertTrue(any(block.get("text", "").strip() for block in option), key)
                marks = [block for block in stem + sum(options, []) if session.LABEL_RE.fullmatch(block.get("text", ""))]
                self.assertEqual(marks, [], key)  # `**N번**` 문단은 번호 배지가 대신하므로 어디에도 남지 않음
        q5, q20 = (self.sess.cat[key] for key in ("s04/Q5", "s04/Q20"))
        stem, options = session.split_choices(adaptive.quiz_section(q5["set"], q5["q"]["id"]))  # 보기가 코드 블록인 번호 목록
        self.assertEqual([[block["t"] for block in option] for option in options], [["code"]] * 4)
        self.assertIn("t.insert(0, 'X')", options[3][0]["text"])
        self.assertNotIn("ol", [block["t"] for block in stem])
        stem, options = session.split_choices(adaptive.quiz_section(q20["set"], q20["q"]["id"]))  # `**N번**` 문단
        self.assertEqual(([block["t"] for block in stem], [[block["t"] for block in option] for option in options]), (["para"], [["code"]] * 5))
        self.assertIn("a[len(a)] = 4", options[1][0]["text"])

    def test_choice_body_that_cannot_be_split_is_left_whole(self):
        def shape(body):
            stem, options = session.split_choices(body)
            return [block.get("text", block["t"]) for block in stem], [[block.get("text", block["t"]) for block in option] for option in options]

        self.assertEqual(shape("지문\n\n1. 가\n2. 나\n\n덧붙임"), (["지문", "덧붙임"], [["가"], ["나"]]))
        self.assertEqual(shape("순서\n\n1. 하나\n2. 둘\n\n고르세요.\n\n1. 가\n2. 나\n3. 다"),
                         (["순서", "ol", "고르세요."], [["가"], ["나"], ["다"]]))  # 보기는 마지막 번호 목록
        self.assertEqual(shape("지문\n\n**1번**\n\n첫째\n\n둘째 문단\n\n**2번**\n\n```\nx\n```"), (["지문"], [["첫째", "둘째 문단"], ["x"]]))
        for body in ("보기가 없는 글", "**1번**\n\n가\n\n**2번**\n\n나", "지문\n\n**1번**\n\n**2번**\n\n나", "1. 가\n2. 나"):
            self.assertEqual(session.split_choices(body), ([], []), body)  # 지문이나 보기가 비면 나누지 않음
        self.assertEqual(session.choice_count("지문\n\n**1번**\n\n**2번**\n\n나"), 2)  # 이때 화면은 본문 전체와 번호만 든 카드를 보여 줌

    def test_try_run_shows_prints_made_inside_a_function(self):
        spec = next(it["spec"] for it in self.sess.cat.values() if it["kind"] == "code" and it["spec"]["mode"] == "call")
        path = os.path.join(self.tmp, "sol.py")
        study.write_text(path, "def solution(*args, **kw):\n    print('디버그', len(args))\n    return None\n")
        run = study.run_cases(spec, path, limit=1)
        self.assertIn("디버그", run["cases"][0]["printed"])
        self.assertFalse(run["cases"][0]["ok"])

    def test_write_text_cleans_up_when_replace_fails(self):
        target = os.path.join(self.tmp, "locked.txt")
        study.write_text(target, "원래 내용")
        real = os.replace

        def always_locked(src, dst):
            raise PermissionError("잠김")

        os.replace = always_locked
        try:
            with self.assertRaises(PermissionError):
                study.write_text(target, "새 내용")
        finally:
            os.replace = real
        self.assertEqual(study.read_text(target), "원래 내용")
        self.assertEqual(os.listdir(self.tmp).count("locked.txt"), 1)
        self.assertEqual([f for f in os.listdir(self.tmp) if ".tmp" in f], [])

    def test_unknown_round_or_item_raises_readable_error(self):
        self.sess.ensure_round()
        for call in (lambda: self.sess.open_round("r99"), lambda: self.sess.set_answer("d1", "nope", 1),
                     lambda: self.sess.try_run("d1", self.sess.open_round("d1")["items"][0]["id"])):
            with self.assertRaises(session.SessionError):
                call()


class RoundPointsTest(unittest.TestCase):
    """회차 배점. 문항 가중치(유형·레벨)에 비례해 100점을 나눔."""

    WEIGHTS = {("choice", 1): 2, ("choice", 2): 3, ("choice", 3): 4, ("short", 1): 3, ("short", 2): 4, ("short", 3): 5,
               ("output", 1): 3, ("output", 2): 4, ("output", 3): 5, ("code", 1): 4, ("code", 2): 6, ("code", 3): 8}

    @classmethod
    def setUpClass(cls):
        adaptive.clear_cache()
        cls.cat = adaptive.catalog()

    def test_weight_follows_type_and_level(self):
        for key, it in self.cat.items():
            kind = it["type"] if it["kind"] == "quiz" else "code"
            self.assertEqual(adaptive.item_weight(it), self.WEIGHTS[(kind, it["level"])], key)

    def test_points_add_up_to_100_and_heavier_items_never_get_less(self):
        rng = random.Random(5)
        keys = sorted(self.cat)
        for _ in range(300):
            picked = rng.sample(keys, rng.randint(1, 40))
            points = adaptive.round_points(picked + ["s99/Q1"], self.cat)  # 카탈로그에 없는 문항은 빠짐
            self.assertEqual(list(points), picked)
            self.assertEqual(sum(points.values()), 100)
            self.assertGreaterEqual(min(points.values()), 1)
            for a in picked:
                for b in picked:
                    if adaptive.item_weight(self.cat[a]) > adaptive.item_weight(self.cat[b]):
                        self.assertGreaterEqual(points[a], points[b], (a, b))
        self.assertEqual(adaptive.round_points([], self.cat), {})
        self.assertEqual(adaptive.round_points(["s99/Q1"], self.cat), {})

    def test_remainder_goes_to_the_largest_fraction_then_item_order(self):
        cat = {"c": {"kind": "quiz", "points": 2, "level": 1}, "h": {"kind": "code", "points": 8, "level": 3},
               "s1": {"kind": "quiz", "points": 3, "level": 1}, "s2": {"kind": "quiz", "points": 3, "level": 1},
               "s3": {"kind": "quiz", "points": 3, "level": 1}}
        self.assertEqual(adaptive.round_points(["c", "h"], cat), {"c": 20, "h": 80})
        self.assertEqual(adaptive.round_points(["s2", "s1", "s3"], cat), {"s2": 34, "s1": 33, "s3": 33})
        self.assertEqual(adaptive.round_points(["c", "s1", "h"], cat), {"c": 15, "s1": 23, "h": 62})  # 15.38, 23.08, 61.54

    def test_every_item_gets_at_least_one_point(self):
        """내림하면 0점이 되는 가벼운 문항은 1점을 받고, 남은 99점을 나머지가 나눔."""
        cat = {"light": {"kind": "quiz", "points": 2, "level": 1}}
        cat.update({"h%02d" % n: {"kind": "code", "points": 8, "level": 3} for n in range(60)})
        points = adaptive.round_points(list(cat), cat)
        self.assertEqual((points["light"], sum(points.values())), (1, 100))
        self.assertEqual(sorted(set(points[k] for k in cat if k != "light")), [1, 2])


if __name__ == "__main__":
    unittest.main()
