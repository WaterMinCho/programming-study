# -*- coding: utf-8 -*-
"""여정 결과 칸의 HTML(gui/journey_html.py). PyQt 없이 돎. [코드 실행]과 [제출 후 채점하기]의 문구, 숫자 꼴
(0.42ms, 10.3MB, 합계: 88.5 / 100.0), 값 표기가 고른 언어를 따르는지를 봄. 자식 프로세스는 띄우지 않고 runner 를 가짜로 바꿔 끼움."""
import contextlib
import html
import os
import re
import sys
import unittest
from unittest import mock

os.environ.setdefault("STUDY_NODE_PROBE", "0")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import study  # noqa: E402
from gui import journey_html  # noqa: E402
from journey import grading, runner, values  # noqa: E402

LIMIT_NOTE = "채점에서는 Python 3초, JavaScript 3.5초 안에 끝나야 합니다."
PROBLEM = {"signature": {"params": [{"name": "records", "type": "list[str]"}, {"name": "flag", "type": "bool"}],
                         "returns": "list[str]"},
           "time_limit_ms": {"python": 3000, "javascript": 3500},
           "examples": [{"args": [["salt 1", "mint 2"], True], "expected": ["salt", "mint"]},
                        {"args": [["anise 3"], False], "expected": []}]}


def plain(markup):
    """HTML 을 화면에 보이는 글처럼 바꿈. 문단은 줄로 나눔."""
    text = re.sub(r"</p>|<br/?>|</tr>", "\n", markup)
    return html.unescape(re.sub(r"<[^>]+>", "", text))


def raw(status="pass", got=None, ms=0.4213, mb=10.3125, **fields):
    """runner.run_case 가 돌려주는 결과 하나."""
    result = runner.empty_result()
    result.update(status=status, elapsed_ms=ms, peak_mb=mb, **fields)
    if got is not None:
        result["values"] = [values.canonical(got)]
    return result


def fake_runs(raws):
    """runner.run_cases 대신 raws 를 차례로 on_case 에 넘김."""
    def run_cases(lang, source_path, cases, workers=1, on_case=None, cancel=None, node=None, python=None, workdir=None):
        picked = raws[:len(cases)]
        for index, each in enumerate(picked):
            on_case(index, each)
        return picked
    return run_cases


def run_case(no, status, **fields):
    case = {"no": no, "source": "example", "args_text": '["pepper 3"], 2', "want_text": "['pepper']", "got_text": "",
            "status": status, "ok": status == "pass", "ms": 0.4213, "mb": 10.3125, "printed": "", "printed_cut": False,
            "error": "", "note": ""}
    case.update(fields)
    return case


def grade_case(no, status, ms=0.4213, mb=10.3125, count=None, name=None):
    return {"no": no, "id": "t%d" % no, "status": status, "label": grading.label(status, ms, mb, count), "ms": ms, "mb": mb,
            "count": count, "name": name}


class RunHtmlTest(unittest.TestCase):
    def shown(self, cases, **fields):
        result = {"lang": "python", "runtime": "Python 3.14.4", "fatal": None, "cases": cases,
                  "passed": sum(1 for case in cases if case["ok"]), "total": len(cases), "cancelled": False,
                  "limit_note": LIMIT_NOTE}
        result.update(fields)
        return plain(journey_html.run_html(result))

    def test_passing_case_shows_every_line_and_the_measures(self):
        text = self.shown([run_case(1, "pass", got_text="['pepper']", printed="안녕\n")])
        for line in ("테스트 1", "입력값 〉 [\"pepper 3\"], 2", "기댓값 〉 ['pepper']", "실행 결과 〉 테스트를 통과하였습니다.",
                     "시간·메모리 〉 0.42ms, 10.3MB", "출력 〉", "안녕", "테스트 결과 1개 중 1개 성공", LIMIT_NOTE):
            self.assertIn(line, text)

    def test_failure_messages_follow_programmers(self):
        cases = [run_case(1, "wrong", got_text="['mint', 'clove', 'basil']", want_text="['basil', 'clove', 'mint']"),
                 run_case(2, "bad_return", note=values.TUPLE_NOTE),
                 run_case(3, "runtime", error="ZeroDivisionError: division by zero (3번째 줄)", note=""),
                 run_case(4, "timeout"), run_case(5, "memory")]
        text = self.shown(cases)
        self.assertIn("기댓값 〉 ['basil', 'clove', 'mint']\n실행 결과 〉 기댓값과 다릅니다. 실행한 결괏값: ['mint', 'clove', 'basil']", text)
        self.assertIn("실행 결과 〉 기댓값과 다릅니다.\n참고 〉 " + values.TUPLE_NOTE, text)
        self.assertIn("실행 결과 〉 실행 중 오류가 발생했습니다.\nZeroDivisionError: division by zero (3번째 줄)", text)
        self.assertIn("실행 시간이 %.1f초를 초과하여 실행이 중단되었습니다." % (runner.RUN_LIMIT_MS / 1000.0), text)
        self.assertIn("10.0초", text)
        self.assertIn("메모리를 %dMB 넘게 써서 실행이 중단되었습니다." % study.MEMORY_LIMIT_MB, text)
        self.assertIn("테스트 결과 5개 중 0개 성공", text)
        self.assertEqual(2, text.count("시간·메모리 〉"), "시간은 끝까지 돈 줄(틀림, 반환형 거부)에만 보임")

    def test_fatal_shows_one_line_without_cases(self):
        text = self.shown([], fatal={"kind": "syntax", "message": "SyntaxError: '(' was never closed", "line": 2, "note": ""})
        self.assertIn("SyntaxError: '(' was never closed (2번째 줄)", text)
        self.assertNotIn("테스트 1", text)
        self.assertNotIn("성공", text)
        text = self.shown([], fatal={"kind": "no_solution", "message": "solution 함수가 없습니다.", "line": None, "note": ""})
        self.assertIn("solution 함수가 없습니다.", text)
        self.assertNotIn("번째 줄", text)

    def test_markup_in_values_and_output_is_escaped(self):
        markup = journey_html.run_html({"cases": [run_case(1, "pass", printed="<b>굵게</b>\n", args_text="'<i>'")], "passed": 1,
                                         "total": 1, "limit_note": LIMIT_NOTE})
        self.assertNotIn("<b>굵게", markup)
        self.assertIn("&lt;b&gt;굵게", markup)
        self.assertIn("'&lt;i&gt;'", markup)

    def test_partial_and_cancelled(self):
        partial = plain(journey_html.run_html({"cases": [run_case(1, "pass")]}, done=False))
        self.assertIn("테스트 1", partial)
        self.assertNotIn("성공", partial)
        stopped = self.shown([run_case(1, "pass")], cancelled=True)
        self.assertIn(journey_html.STOPPED_RUN, stopped)
        self.assertNotIn("성공", stopped)

    def test_values_follow_the_language(self):
        """grading.run 이 만든 줄을 그대로 그림. Python 은 repr 꼴, JavaScript 는 JSON 꼴."""
        raws = [raw("pass", got=["salt", "mint"]), raw("wrong", got=["anise"]), raw("pass", got=[])]
        shown = {}
        for lang in values.LANGS:
            with mock.patch.object(runner, "run_cases", fake_runs(raws)):
                result = grading.run(PROBLEM, lang, "solution", [{"args": [["x 1"], False], "expected": []}])
            shown[lang] = plain(journey_html.run_html(result))
        python, script = shown["python"], shown["javascript"]
        self.assertIn("입력값 〉 ['salt 1', 'mint 2'], True", python)
        self.assertIn("입력값 〉 [\"salt 1\", \"mint 2\"], true", script)
        self.assertIn("기댓값과 다릅니다. 실행한 결괏값: ['anise']", python)
        self.assertIn("기댓값과 다릅니다. 실행한 결괏값: [\"anise\"]", script)
        self.assertIn("테스트 결과 3개 중 2개 성공", python)
        self.assertNotIn("True", script)


class GradeHtmlTest(unittest.TestCase):
    def result(self, **fields):
        accuracy = [grade_case(1, "pass"), grade_case(2, "wrong", ms=0.0213, mb=10.2),
                    grade_case(3, "pass", ms=0.4213, mb=15.3, count=50), grade_case(4, "runtime")]
        efficiency = [grade_case(1, "pass", ms=76.2149, mb=98.4), grade_case(2, "timeout"), grade_case(3, "memory")]
        result = {"lang": "python", "runtime": "Python 3.14.4", "fatal": None, "cancelled": False,
                  "groups": [{"name": "정확성", "points": 70.0, "earned": 56.5, "cases": accuracy},
                             {"name": "효율성", "points": 30.0, "earned": 32.0, "cases": efficiency}],
                  "acc": 56.5, "eff": 32.0, "score": 88.5, "passed": False, "first_pass": False, "boss_opened": False,
                  "cleared": False}
        result.update(fields)
        return result

    def test_groups_lines_and_total(self):
        text = plain(journey_html.grade_html(self.result()))
        for line in ("정확성 테스트", "테스트 1 〉 통과 (0.42ms, 10.3MB)", "테스트 2 〉 실패 (0.02ms, 10.2MB)",
                     "테스트 3 〉 통과 (0.42ms, 15.3MB) · 50건", "테스트 4 〉 실패 (런타임 에러)", "효율성 테스트",
                     "테스트 1 〉 통과 (76.21ms, 98.4MB)", "테스트 2 〉 실패 (시간 초과)", "테스트 3 〉 실패 (메모리 초과)",
                     "채점 결과", "정확성: 56.5", "효율성: 32.0", "합계: 88.5 / 100.0", "Python 3.14.4로 실행했습니다.",
                     journey_html.MEMORY_NOTE):
            self.assertIn(line, text)
        self.assertLess(text.index("정확성 테스트"), text.index("효율성 테스트"))
        self.assertLess(text.index("효율성 테스트"), text.index("합계"))
        self.assertNotIn("처음으로 통과", text)

    def test_first_pass_and_boss_opened(self):
        markup = journey_html.grade_html(self.result(first_pass=True, boss_opened=True, score=100.0))
        text = plain(markup)
        self.assertIn("합계: 100.0 / 100.0", text)
        self.assertIn("처음으로 통과했습니다. 해설을 볼 수 있습니다.", text)
        self.assertIn("보스 문제가 열렸습니다. 보스에 도전하기", text)
        self.assertIn('href="%s"' % journey_html.BOSS_LINK, markup)

    def test_revealed_name_follows_the_failed_line(self):
        result = self.result()
        result["groups"][0]["cases"][1]["name"] = "k가 품목 수보다 큼"
        self.assertIn("테스트 2 〉 실패 (0.02ms, 10.2MB) · k가 품목 수보다 큼", plain(journey_html.grade_html(result)))

    def test_fatal_has_no_lines_and_zero_total(self):
        fatal = {"kind": "syntax", "message": "SyntaxError: invalid syntax", "line": 3, "note": ""}
        text = plain(journey_html.grade_html(self.result(fatal=fatal, groups=[], score=0.0)))
        self.assertIn("SyntaxError: invalid syntax (3번째 줄)", text)
        self.assertIn("합계: 0.0 / 100.0", text)
        self.assertNotIn("테스트 1 〉", text)
        self.assertNotIn("정확성:", text)

    def test_partial_and_cancelled(self):
        partial = plain(journey_html.grade_html({"groups": [{"name": "정확성", "cases": [grade_case(1, "pass")]}]}, done=False))
        self.assertIn("테스트 1 〉 통과 (0.42ms, 10.3MB)", partial)
        self.assertNotIn("합계", partial)
        stopped = self.result(cancelled=True)
        stopped["groups"][1]["cases"][2] = grade_case(3, "cancelled")
        text = plain(journey_html.grade_html(stopped))
        self.assertIn("테스트 3 〉 취소됨", text)
        self.assertIn(journey_html.STOPPED_GRADE, text)
        self.assertNotIn("합계", text)

    def test_grading_result_renders_with_the_same_numbers(self):
        """grading.grade 가 만든 결과(점수 반올림, 묶음 줄)를 그대로 그림. 실행기는 가짜임."""
        tests = {"accuracy": [{"id": "big", "name": "큰 수", "args": [["a 1"], True], "expected": ["a"]},
                              {"id": "rand1", "name": "소형 무작위 1", "args": [["b 1"], True], "count": 50, "expected": ["b"]}],
                 "efficiency": [{"id": "many", "args": [["c 1"], True], "expected": ["c"]}]}
        raws = [raw("pass"), raw("wrong"), raw("pass"), raw("pass", ms=0.0049, mb=16.64), raw("timeout", ms=None, mb=None)]
        accuracy, efficiency = raws[:4], raws[4:]

        def run_cases(lang, source_path, cases, workers=1, on_case=None, cancel=None, node=None, python=None, workdir=None):
            picked = accuracy if len(cases) == 4 else efficiency
            for index, each in enumerate(picked):
                on_case(index, each)
            return picked

        with mock.patch.object(runner, "workspace", lambda: contextlib.nullcontext(os.getcwd())), \
                mock.patch.object(runner, "prepare", lambda *args: None), mock.patch.object(runner, "run_cases", run_cases):
            result = grading.grade(PROBLEM, "mid", tests, None, "python", "solution", reveal=True)
        text = plain(journey_html.grade_html(result))
        self.assertIn("테스트 2 〉 실패 (0.42ms, 10.3MB) · 입출력 예 2", text)
        self.assertIn("테스트 4 〉 통과 (0.00ms, 16.6MB) · 50건", text)
        self.assertIn("테스트 1 〉 실패 (시간 초과)", text)
        self.assertIn("정확성: 45.0", text)  # 중급 60점 × 3/4
        self.assertIn("효율성: 0.0", text)
        self.assertIn("합계: 45.0 / 100.0", text)


if __name__ == "__main__":
    unittest.main()
