# -*- coding: utf-8 -*-
"""터미널 명령 `python study.py web …` 테스트. 설계 1.4 의 성공 기준 1(미션 하나를 받기부터 해설까지)과 2(사슬 하나를 답 시간,
자기 채점, 다음 복습 날짜까지)를 명령만으로 끝내 봄. 출력·입력·시계는 가짜로 바꾸고 vitest 는 test_web_service 의
FakeVitest 를 씀. 창·터미널·편집기는 열지 않음.

실행: python -m unittest tests.test_web_cli
"""
import os
import sys
import unittest
from unittest import mock

os.environ.setdefault("STUDY_NODE_PROBE", "0")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import study  # noqa: E402
from webprep import cli, stack  # noqa: E402
from tests.test_web_service import Base  # noqa: E402


class CliBase(Base):
    def setUp(self):
        super().setUp()
        self.answers = []
        self.asked = []
        self.lines = []
        self.seconds = 0.0
        self.step = 7.0

    def ask(self, prompt):
        self.asked.append(prompt)
        return self.answers.pop(0) if self.answers else ""

    def monotonic(self):
        self.seconds += self.step
        return self.seconds

    def cmd(self, *argv, answers=()):
        self.answers = list(answers)
        self.lines = []
        code = cli.main(list(argv) + ["--user", "alice"], out=self.lines.append, ask=self.ask, clock=self.monotonic,
                        repo=self.repo, home=self.home)
        return code, "\n".join(self.lines)


class MissionCliTest(CliBase):
    def test_mission_from_get_to_explanation(self):
        code, text = self.cmd("get", "x01")
        self.assertEqual(0, code)
        self.assertIn("과제를 받았습니다", text)
        self.assertIn("읽기 시간 2분", text)
        self.assertIn("# x01. 횟수 세기 버튼", text)
        self.assertTrue(os.path.isfile(self.app_path()))

        code, text = self.cmd("start", "x01", answers=["y"])
        self.assertEqual(0, code)
        self.assertIn("AI 자동완성을 껐나요", self.asked[-1])
        self.assertIn("실전 시간 6분", text)
        self.assertIn("0단계. 코드 설명 (목표 1분)", text)
        self.assertTrue(self.log()[-1]["no_ai"])

        code, text = self.cmd("check", "x01", answers=["1"])
        self.assertEqual(0, code)
        self.assertIn("0단계에는 자동 검사가 없습니다", text)
        self.assertIn("1. 횟수가 `App`의 state 에 있다고 말했습니다.", text)
        self.assertIn("1단계. 더하기 버튼 (목표 2분)", text)
        self.assertIn("검사는 아래 내용을 확인합니다.", text)
        self.assertEqual([1, 0], self.log()[-1]["said"])

        code, text = self.cmd("check", "x01")
        self.assertEqual(0, code)
        self.assertIn("1a  실패", text)
        self.assertIn("Unable to find role button", text)
        self.assertNotIn("<body />", text)  # DOM 덤프는 접어 둠
        self.assertIn("검사 2개 가운데 0개 통과", text)
        self.assertIn("아직 통과하지 않았습니다", text)

        code, text = self.cmd("hint", "x01")
        self.assertEqual(0, code)
        self.assertIn("면접관 힌트 1:", text)
        code, text = self.cmd("hint", "x01")
        self.assertEqual(1, code)
        self.assertIn("오류: 이 단계의 힌트를 모두 들었습니다.", text)

        code, text = self.cmd("skip", "x01")
        self.assertEqual(1, code)
        self.assertIn("2분이 지나야", text)

        self.solve(1)
        code, text = self.cmd("check", "x01")
        self.assertEqual(0, code)
        self.assertIn("1a  통과", text)
        self.assertIn("1단계를 통과했습니다.", text)
        self.assertIn("2단계. 초기화 버튼 (목표 2분)", text)

        self.solve(2)
        code, text = self.cmd("check", "x01", answers=["", "1 2"])
        self.assertEqual(0, code)
        self.assertIn("2단계를 통과했습니다.", text)
        self.assertIn("30초 안에 소리 내어 답하세요", text)
        self.assertIn("면접관: 초기화 버튼을 눌렀을 때", text)
        self.assertIn("답 시간: 7초 (30초 안)", text)
        self.assertIn("1. [필수] `App` 함수가", text)
        self.assertIn("판정: 통과", text)
        self.assertIn("모든 단계를 끝냈습니다", text)
        self.assertEqual(["check", "step", "finish", "after"], self.kinds()[-4:])

        code, text = self.cmd("finish", "x01", answers=["1 3 5"])
        self.assertEqual(0, code)
        self.assertIn("x01 횟수 세기 버튼 끝남 (1번째 시도)", text)
        self.assertIn("0단계 코드 설명", text)
        self.assertIn("통과 (힌트 1)", text)
        self.assertIn("## 모범 답안", text)
        self.assertIn("(같습니다)", text)
        self.assertIn("템플릿에서 모범 답안까지 바뀐 파일: src/App.tsx", text)
        self.assertIn("스스로 점검", text)
        self.assertIn("꼬리 질문: `python study.py web drill x01-F`", text)
        self.assertIn("`python study.py web show l90`", text)
        self.assertEqual({"c1": 1, "c2": 0, "c3": 1, "m1": 0, "m2": 1}, self.log()[-1]["ticks"])

        code, text = self.cmd("finish", "x01", "--self", "2")
        self.assertEqual(0, code)
        self.assertIn("2. [v]", text)
        self.assertEqual(["self", "self"], self.kinds()[-2:])

    def test_check_before_live_and_unknown_mission(self):
        code, text = self.cmd("check", "x01")
        self.assertEqual((1, "오류: 실전 중이 아닙니다(지금 받기 전)."), (code, text))
        code, text = self.cmd("get", "x02")
        self.assertEqual(1, code)
        self.assertIn("아직 출제되지 않은", text)
        code, text = self.cmd("get", "x01")
        code, text = self.cmd("get", "x01")
        self.assertEqual(1, code)
        self.assertIn("--again", text)

    def test_skip_after_target_time(self):
        self.cmd("get", "x01")
        self.cmd("start", "x01", "--no-ai", "no")
        self.assertFalse(self.log()[-1]["no_ai"])
        self.cmd("check", "x01", "--said", "1,2")
        self.assertEqual([1, 1], self.log()[-1]["said"])
        self.tick(minutes=2)
        code, text = self.cmd("skip", "x01")
        self.assertEqual(0, code)
        self.assertIn("1단계를 넘어갔습니다", text)
        self.assertIn("2단계. 초기화 버튼", text)
        self.tick(minutes=2)
        code, text = self.cmd("skip", "x01")
        self.assertIn("모든 단계를 끝냈습니다", text)
        code, text = self.cmd("finish", "x01", "--self", "")
        self.assertIn("넘어감", text)
        self.assertIn("초기화", text)  # 내 코드와 모범 답안의 차이에 초기화 버튼이 나옴

    def test_check_without_stack_explains_install(self):
        self.cmd("get", "x01")
        self.cmd("start", "x01", "--no-ai", "yes")
        self.cmd("check", "x01", "--said", "")
        os.remove(os.path.join(self.repo, stack.VITEST_MJS))
        code, text = self.cmd("check", "x01")
        self.assertEqual(1, code)
        self.assertIn("web install", text)

    def test_status_counts_passed_steps_against_required_steps(self):
        web = self.to_live(self.session())
        self.tick(minutes=3)
        web.skip("x01")
        self.solve(2)
        web.check("x01")  # 마지막 2단계를 통과하면 끝남
        code, text = self.cmd("status")
        self.assertEqual(0, code)
        self.assertIn("끝남 1/2", text)  # 0단계는 세지 않고 넘어간 1단계는 통과가 아님


class DrillCliTest(CliBase):
    def test_chain_with_timer_marks_and_next_review(self):
        self.step = 31.0  # 질문마다 Enter 까지 31초
        code, text = self.cmd("drill", "90-A", answers=["", "1 2", "", "", "", "y", "플래그 변수를 말함", "m", "n", ""])
        self.assertEqual(0, code, text)
        self.assertIn("사슬 90-A. 버튼을 눌렀는데 화면이 그대로일 때", text)
        self.assertIn("```tsx", text)
        self.assertIn("Q1. 버튼을 눌러도 화면의 숫자가 바뀌지 않습니다.", text)
        self.assertIn("60초 안에 소리 내어 답한 뒤 Enter", self.asked[0])
        self.assertIn("답 시간: 31초 (60초 안)", text)
        self.assertIn("1. [필수] `count`는 바뀌지만", text)
        self.assertIn("2. [보충] 컴포넌트 함수를 다시 실행해", text)
        self.assertIn("막히면: 값을 바꾼 뒤 React 에", text)
        self.assertIn("막힌 곳에서 아는 데까지 말했나요", "\n".join(self.asked))
        self.assertIn("약한 답", text)
        self.assertIn('> "리렌더링이 안 돼서 그렇습니다."', text)
        self.assertIn("이어 말하기", text)
        self.assertIn("사슬 결과: 막힘 (질문별 통과, 막힘, 막힘)", text)
        self.assertIn("상자 1, 다음 복습 2026-10-22", text)
        self.assertIn("`python study.py web show l90` (90a 절)", text)
        drills = [e for e in self.log() if e["kind"] == "drill"]
        self.assertEqual([(1, 31, [1], [1], None, ""), (2, 31, [0], [], 1, "플래그 변수를 말함"), (3, 31, [0], [0], 0, "")],
                         [(e["q"], e["secs"], e["need"], e["extra"], e["talked"], e["note"]) for e in drills])
        self.assertEqual({"kind": "chain", "chain": "90-A", "result": "stuck"}, {k: self.log()[-1][k] for k in ("kind", "chain", "result")})

        self.clock = "2026-10-22T09:00:00"
        code, text = self.cmd("drill", "90-A", answers=["", "1", "", "", "1", "", "", "1", ""])
        self.assertEqual(0, code, text)
        self.assertIn("상자 1, 2번째 복습", text)
        self.assertIn("(지난 답: 플래그 변수를 말함)", text)
        self.assertIn("사슬 결과: 통과 (질문별 통과, 통과, 통과)", text)
        self.assertIn("상자 2, 다음 복습 2026-10-25", text)

    def test_drill_without_chain_takes_first_due(self):
        code, text = self.cmd("drill", answers=["", "1", "", "", "1", "", "", "1", ""])
        self.assertEqual(0, code, text)
        self.assertIn("사슬 90-A.", text)
        self.assertIn("사슬 결과: 통과", text)
        code, text = self.cmd("drill", answers=["", "1", "", "", "1", ""])
        self.assertIn("사슬 90-B.", text)
        code, text = self.cmd("drill")
        self.assertEqual(0, code)
        self.assertIn("오늘 복습할 사슬이 없습니다", text)

    def test_time_over_is_reported(self):
        self.step = 75.0
        code, text = self.cmd("drill", "90-B", answers=["", "1", "", "", "1", ""])
        self.assertIn("답 시간: 75초 (30초 넘김)", text)  # 90-B 는 45초
        self.assertEqual(75, [e for e in self.log() if e["kind"] == "drill"][0]["secs"])


class StatusInstallCliTest(CliBase):
    def test_status(self):
        code, text = self.cmd("status")
        self.assertEqual(0, code)
        self.assertIn("Node.js 22.23.2", text)
        self.assertIn("검사 도구 설치됨", text)
        self.assertIn("x01  횟수 세기 버튼", text)
        self.assertIn("받기 전", text)
        self.assertIn("x02  준비 중 미션", text)
        self.assertIn("90-A", text)
        self.assertIn("새 사슬", text)
        self.assertIn("오늘 복습 (약 8분)", text)
        self.assertIn("다음 추천: l90", text)
        self.node = None
        code, text = self.cmd("status")
        self.assertIn("Node.js 없음", text)
        self.assertIn("Node.js 22.12 이상", text)

    def test_install_asks_for_consent(self):
        fake = mock.Mock(return_value={"ok": True, "message": "검사 도구를 설치했습니다(3초).", "seconds": 3.0, "log": "x"})
        with mock.patch.object(stack, "install", fake):
            code, text = self.cmd("install", answers=["n"])
            self.assertEqual(1, code)
            self.assertIn("약 80MB", text)
            self.assertIn("설치하지 않았습니다.", text)
            self.assertEqual(0, fake.call_count)
            code, text = self.cmd("install", answers=["y"])
            self.assertEqual(0, code)
            self.assertIn("설치했습니다(3초)", text)
            code, text = self.cmd("install", "--yes")
            self.assertEqual(0, code)
            self.assertEqual(2, fake.call_count)
        with mock.patch.object(stack, "install", return_value={"ok": False, "message": "설치가 실패했습니다(종료 코드 1). 로그: x", "seconds": 1.0, "log": "x"}):
            code, text = self.cmd("install", "--yes")
            self.assertEqual(1, code)
            self.assertIn("오류: 설치가 실패했습니다", text)
        code, text = self.cmd("uninstall")
        self.assertEqual(0, code)
        self.assertIn("지웠습니다", text)

    def test_show_and_help_and_user_resolution(self):
        code, text = self.cmd("show", "l90")
        self.assertEqual(0, code)
        self.assertIn("# state 가 바뀌면", text)
        self.assertIn("[그림] 그림 1.", text)
        self.assertEqual("learn", self.kinds()[-1])
        lines = []
        self.assertEqual(0, cli.main([], out=lines.append))
        self.assertIn("python study.py web status", "\n".join(lines))
        lines = []
        self.assertEqual(0, cli.main(["--help"], out=lines.append))
        lines = []
        with mock.patch.dict(os.environ, {"STUDY_USER": ""}), mock.patch.object(study, "USER_FILE", os.path.join(self.tmp, "nouser")):
            code = cli.main(["status"], out=lines.append, repo=self.repo, home=self.home)
        self.assertEqual(1, code)
        self.assertIn("내 ID 를 모릅니다", "\n".join(lines))
        lines = []
        code = cli.main(["--user", "bob", "show", "l90"], out=lines.append, repo=self.repo, home=self.home)
        self.assertEqual(0, code)
        self.assertEqual("learn", self.kinds("bob")[-1])

    def test_study_main_routes_web_to_cli(self):
        with mock.patch.object(cli, "main", return_value=0) as fake:
            with self.assertRaises(SystemExit) as stop:
                study.main(["web", "status", "--user", "alice"])
        self.assertEqual(0, stop.exception.code)
        self.assertEqual((["status", "--user", "alice"],), fake.call_args[0])


if __name__ == "__main__":
    unittest.main()
