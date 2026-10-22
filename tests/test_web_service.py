# -*- coding: utf-8 -*-
"""WebSession 테스트. 고정 은행 tests/web_bank 와 임시 submissions·홈 폴더, 가짜 Node·가짜 vitest 로 미션 흐름(받기→실전→
단계 검사→힌트·넘어가기→끝남·해설)과 드릴 흐름(답 기록→사슬 판정→복습 상자), 오늘 복습, 현황을 봄.
실제 vitest 를 돌리는 통합 테스트는 저장소 맨 위에 node_modules 가 있고 Node 22.12 이상이 있을 때만 돎.

실행: python -m unittest tests.test_web_service
"""
import datetime
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
import study  # noqa: E402
from webprep import bank, checks, service, stack  # noqa: E402
from webprep.service import WebError, WebSession  # noqa: E402

FIXTURE = os.path.join(ROOT, "tests", "web_bank")
FAKE_NODE = {"path": "/fake/node", "version": "22.23.2", "major": 22}
REAL_NODE = None if os.environ.get("STUDY_LEAN_CI") else stack.find_node()
HAS_STACK = os.path.isfile(os.path.join(ROOT, stack.VITEST_MJS))


class FakeVitest(object):
    """checks._popen 자리. 설정 파일에서 학습자 폴더와 돌릴 단계 파일을 읽고, App.tsx 에 "더하기"가 있으면 1단계,
    "초기화"가 있으면 2단계를 통과시키는 vitest JSON 보고서를 씀."""

    calls = []

    def __init__(self, cmd, **options):
        FakeVitest.calls.append((cmd, options))
        self.returncode = 0
        config = study.read_text(cmd[cmd.index("--config") + 1])
        out = [a for a in cmd if a.startswith("--outputFile=")][0].split("=", 1)[1]
        app = re.search(r"'@app': \"(.*?)\"", config).group(1)
        src = study.read_text(os.path.join(app, "App.tsx"))
        results = []
        for rel in re.findall(r'"([^"]*(?:step\d|hidden)\.test\.tsx)"', config):
            path = os.path.join(options["cwd"], *rel.split("/"))
            ids = bank.check_ids(study.read_text(path))
            found = re.search(r"step(\d)", rel)
            ok = True if not found else (("더하기" in src) if found.group(1) == "1" else ("초기화" in src))
            rows = []
            for cid in ids:
                rows.append({"ancestorTitles": [], "fullName": cid, "title": "%s 검사 %s" % (cid, cid), "duration": 10,
                             "status": "passed" if ok else "failed",
                             "failureMessages": [] if ok else ["TestingLibraryElementError: Unable to find role button\n\nIgnored nodes: comments\n<body />"]})
            results.append({"name": path, "status": "passed" if ok else "failed", "message": "", "assertionResults": rows})
        study.write_text(out, json.dumps({"testResults": results}))

    def communicate(self, timeout=None):
        return b"", b""


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="web_service_")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.repo = os.path.join(self.tmp, "repo")
        study.write_text(os.path.join(self.repo, stack.VITEST_MJS), "")
        shutil.copyfile(os.path.join(ROOT, "package-lock.json"), os.path.join(self.repo, "package-lock.json"))
        study.write_text(stack.marker_path(self.repo), stack.lock_hash(self.repo) + "\n")
        self.home = os.path.join(self.tmp, "home")
        self.subs = os.path.join(self.tmp, "submissions")
        for target, name, value in ((study, "SUBMISSIONS_DIR", self.subs), (bank, "BANK_DIR", FIXTURE),
                                    (checks, "_popen", FakeVitest), (service, "now", lambda: self.clock)):
            patcher = mock.patch.object(target, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = mock.patch.object(stack, "find_node", lambda saved=None, probe=False: self.node)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.node = FAKE_NODE
        self.clock = "2026-10-21T09:00:00"
        FakeVitest.calls = []

    def tick(self, minutes=0, seconds=0):
        when = datetime.datetime.fromisoformat(self.clock) + datetime.timedelta(minutes=minutes, seconds=seconds)
        self.clock = when.isoformat(timespec="seconds")

    def session(self, user="alice", repo=None):
        return WebSession(user, repo=repo or self.repo, home=self.home)

    def record_path(self, user="alice"):
        return os.path.join(self.subs, user, "web", "record.json")

    def log(self, user="alice"):
        return study.read_json(self.record_path(user))["log"] if os.path.isfile(self.record_path(user)) else []

    def kinds(self, user="alice"):
        return [e["kind"] for e in self.log(user)]

    def app_path(self, user="alice", mid="x01"):
        return os.path.join(self.subs, user, "web", "missions", mid, "src", "App.tsx")

    def solve(self, upto, user="alice"):
        secrets = bank.load_secrets(os.path.join(FIXTURE, "missions", "x01"))
        for rel, text in bank.solution_files(secrets, upto).items():
            study.write_text(os.path.join(self.subs, user, "web", "missions", "x01", *rel.split("/")), text)

    def to_live(self, web, mid="x01"):
        web.get(mid)
        web.start(mid, no_ai=True)
        web.explain_done(mid, [1, 1])
        return web


class SessionTest(Base):
    def test_bad_user_and_broken_record(self):
        with self.assertRaises(WebError):
            self.session("bad id")
        study.write_text(self.record_path(), "{broken")
        with self.assertRaises(WebError) as caught:
            self.session()
        self.assertIn("record.json", str(caught.exception))

    def test_bank_loads_ready_items_and_chains(self):
        web = self.session()
        self.assertEqual(["x01"], list(web.missions))
        self.assertEqual(["t90"], list(web.topics))
        self.assertEqual(["l90"], list(web.pages))
        self.assertEqual({"90-A", "90-B", "x01-F"}, set(web.chains))
        self.assertEqual("x01", web.chains["x01-F"]["mission"])
        self.assertEqual("l90", web.chains["x01-F"]["page"])
        self.assertEqual([], web.bank_errors)
        with self.assertRaises(WebError) as caught:
            web.mission("x02")
        self.assertIn("아직 출제되지 않은", str(caught.exception))
        with self.assertRaises(WebError):
            web.mission("w99")

    def test_sealed_bank_works_the_same(self):
        root = os.path.join(self.tmp, "sealed")
        shutil.copytree(FIXTURE, root)
        for folder in (os.path.join(root, "missions", "x01"), os.path.join(root, "drills", "t90")):
            study.write_text(os.path.join(folder, "sealed.json"), bank.seal_text(bank.load_secrets(folder), "시험"))
            shutil.rmtree(os.path.join(folder, "work"))
        with mock.patch.object(bank, "BANK_DIR", root):
            web = self.to_live(self.session())
            view = web.mission("x01")
            self.assertEqual("더하기 버튼", view["current"]["title"])
            self.assertEqual(3, len(web.chain("90-A")["questions"]))


class MissionFlowTest(Base):
    def test_get_copies_template_and_records_receive(self):
        web = self.session()
        view = web.get("x01")
        self.assertEqual(("reading", 1), (view["phase"], view["try"]))
        self.assertTrue(os.path.isfile(self.app_path()))
        self.assertTrue(os.path.isfile(os.path.join(self.subs, "alice", "web", "missions", "x01", "package.json")))
        self.assertEqual([{"kind": "receive", "item": "x01", "try": 1, "at": self.clock}], self.log())
        self.assertEqual(2 * 60, view["timers"]["reading_left"])
        self.tick(minutes=3)
        self.assertEqual(-60, web.mission("x01")["timers"]["reading_left"])
        self.assertIsNone(view["current"])
        self.assertEqual(["locked", "locked", "locked"], [s["result"] for s in view["steps"]])
        self.assertEqual("", view["steps"][1]["title"])  # 단계 제목은 열리기 전에 보이지 않음

    def test_get_twice_needs_again_and_starts_a_new_try(self):
        web = self.session()
        web.get("x01")
        study.write_text(self.app_path(), "내 코드")
        with self.assertRaises(service.AlreadyReceived) as caught:
            web.get("x01")
        self.assertEqual("reading", caught.exception.phase)
        self.assertNotIn("--", str(caught.exception))  # 터미널 명령은 cli 가 붙임
        self.assertEqual("내 코드", study.read_text(self.app_path()))
        self.assertTrue(web.received("x01"))
        self.assertEqual(1, web.resume("x01")["try"])  # 받은 것으로 기록돼 있으면 그대로
        os.remove(self.record_path())  # 기록이 사라져 폴더만 남은 경우: 받기 전으로 보이지만 받은 코드가 있음
        web = self.session()
        self.assertTrue(web.received("x01"))
        with self.assertRaises(service.AlreadyReceived) as caught:
            web.get("x01")
        self.assertEqual("none", caught.exception.phase)
        view = web.resume("x01")  # 폴더의 코드를 그대로 두고 받은 것으로 기록함
        self.assertEqual(("reading", 1, "내 코드"), (view["phase"], view["try"], study.read_text(self.app_path())))
        view = web.get("x01", again=True)
        self.assertEqual(2, view["try"])
        self.assertIn("누르기", study.read_text(self.app_path()))
        web.start("x01")
        web.finish("x01")
        with self.assertRaises(WebError):
            web.get("x01")  # 끝난 미션도 다시 하려면 again
        self.assertEqual(3, web.get("x01", again=True)["try"])

    def test_start_requires_reading_and_records_no_ai(self):
        web = self.session()
        with self.assertRaises(WebError):
            web.start("x01")
        web.get("x01")
        view = web.start("x01", no_ai=False)
        self.assertEqual(("live", 0, "코드 설명"), (view["phase"], view["current"]["no"], view["current"]["title"]))
        self.assertFalse(self.log()[-1]["no_ai"])
        self.assertEqual(2, len(view["current"]["self"]))
        self.assertEqual(60, view["timers"]["step_target"])
        with self.assertRaises(WebError):
            web.start("x01")

    def test_explain_done_records_said_and_opens_step_one(self):
        web = self.session()
        web.get("x01")
        web.start("x01")
        with self.assertRaises(WebError) as caught:
            web.check("x01")
        self.assertIn("0단계", str(caught.exception))
        result = web.explain_done("x01", [1])
        self.assertEqual([1, 0], self.log()[-1]["said"])
        self.assertEqual(("done", 0), (self.log()[-1]["result"], self.log()[-1]["step"]))
        self.assertEqual(1, result["next"]["no"])
        self.assertEqual(2, len(result["next"]["checks"]))
        with self.assertRaises(WebError):
            web.explain_done("x01", [1])
        view = web.mission("x01")
        self.assertEqual("open", view["steps"][1]["result"])
        self.assertEqual("더하기 버튼", view["steps"][1]["title"])
        self.assertEqual("", view["steps"][2]["title"])

    def test_check_fails_then_passes_and_opens_next(self):
        web = self.to_live(self.session())
        result = web.check("x01")
        self.assertEqual((1, False, ["1a", "1b"], []), (result["open"], result["passed"], result["fail"], result["pass"]))
        self.assertIn("Unable to find", result["tests"][0]["message"])
        self.assertEqual("check", self.log()[-1]["kind"])
        self.assertEqual(["1a", "1b"], self.log()[-1]["fail"])
        self.assertEqual(1, web.mission("x01")["current"]["no"])
        cmd, options = FakeVitest.calls[-1]
        self.assertEqual(self.repo, options["cwd"])
        self.assertEqual(study.NO_WINDOW, options["creationflags"])
        self.assertIn(os.path.join(self.repo, "node_modules", "vitest", "vitest.mjs"), cmd)
        self.solve(1)
        result = web.check("x01")
        self.assertTrue(result["passed"])
        self.assertEqual(2, result["next"]["no"])
        self.assertIsNone(result["after"])
        self.assertFalse(result["finished"])
        self.assertEqual(["check", "step"], self.kinds()[-2:])
        self.assertEqual({"step": 1, "result": "pass"}, {k: self.log()[-1][k] for k in ("step", "result")})
        self.assertFalse(os.path.exists(os.path.join(self.repo, ".web-check")))

    def test_check_runs_earlier_steps_and_reports_broken_ones(self):
        web = self.to_live(self.session())
        self.solve(1)
        web.check("x01")
        study.write_text(self.app_path(), study.read_text(self.app_path()).replace("더하기", "빼기"))
        result = web.check("x01")
        self.assertEqual((2, False, [1]), (result["open"], result["passed"], result["broken"]))
        self.assertEqual(["1a", "1b", "2a"], result["fail"])
        self.assertEqual(2, web.mission("x01")["current"]["no"])  # 진행은 막지 않음

    def test_last_step_pass_finishes_and_returns_after_question(self):
        web = self.to_live(self.session())
        self.solve(2)
        result = web.check("x01")
        self.assertTrue(result["passed"])
        self.assertEqual(1, result["open"])
        result = web.check("x01")
        self.assertEqual((2, True, True), (result["open"], result["passed"], result["finished"]))
        self.assertEqual((2, 30), (result["after"]["step"], result["after"]["secs"]))
        self.assertTrue(result["after"]["ask"].startswith("면접관: 초기화"))
        self.assertEqual(["check", "step", "finish"], self.kinds()[-3:])
        self.assertIsNone(self.log()[-1]["hidden"])
        answer = web.after_answer("x01", 2, [1], [0], 25)
        self.assertEqual("pass", answer["result"])
        self.assertEqual({"kind": "after", "step": 2, "need": [1], "extra": [0], "secs": 25}, {k: self.log()[-1][k] for k in ("kind", "step", "need", "extra", "secs")})
        self.assertEqual("done", web.mission("x01")["phase"])
        with self.assertRaises(WebError):
            web.check("x01")

    def test_hints_are_recorded_until_exhausted(self):
        web = self.to_live(self.session())
        hint = web.hint("x01")
        self.assertEqual((1, 0), (hint["n"], hint["left"]))
        self.assertIn("접근성 이름", hint["text"])
        self.assertEqual({"kind": "hint", "step": 1, "n": 1}, {k: self.log()[-1][k] for k in ("kind", "step", "n")})
        with self.assertRaises(WebError) as caught:
            web.hint("x01")
        self.assertIn("모두 들었습니다", str(caught.exception))
        self.assertEqual(1, len(web.mission("x01")["current"]["hints"]))
        self.solve(1)
        web.check("x01")
        self.assertEqual((1, 1), (web.hint("x01")["n"], web.hint("x01")["n"] - 1))
        self.assertEqual(2, web.mission("x01")["hint_count"] - 1)

    def test_skip_needs_target_time(self):
        web = self.to_live(self.session())
        with self.assertRaises(WebError) as caught:
            web.skip("x01")
        self.assertIn("2분", str(caught.exception))
        self.tick(minutes=2)
        self.assertTrue(web.mission("x01")["timers"]["can_skip"])
        result = web.skip("x01")
        self.assertEqual((1, 2, False), (result["skipped"], result["next"]["no"], result["finished"]))
        self.assertEqual({"kind": "skip", "step": 1}, {k: self.log()[-1][k] for k in ("kind", "step")})
        self.tick(minutes=2)
        result = web.skip("x01")
        self.assertTrue(result["finished"])
        self.assertEqual("done", web.mission("x01")["phase"])
        self.assertEqual([1, 2], web.mission("x01")["skips"])

    def test_skip_at_step_zero_is_refused(self):
        web = self.session()
        web.get("x01")
        web.start("x01")
        self.tick(minutes=5)
        with self.assertRaises(WebError):
            web.skip("x01")

    def test_timers_follow_the_clock(self):
        web = self.to_live(self.session())
        self.tick(minutes=7)
        timers = web.mission("x01")["timers"]
        self.assertEqual((7 * 60, 60, 7 * 60, 120, 5 * 60), (timers["live_elapsed"], timers["live_over"], timers["step_elapsed"],
                                                           timers["step_target"], timers["step_over"]))
        self.assertIsNone(timers["reading_left"])

    def test_finish_returns_explanation_diffs_and_items(self):
        web = self.to_live(self.session())
        self.solve(1)
        web.check("x01")
        result = web.finish("x01")
        self.assertEqual(["check", "step", "finish"], self.kinds()[-3:])
        self.assertIn("## 모범 답안", result["explain"])
        self.assertEqual(["src/App.tsx"], [r["file"] for r in result["template_diff"]])
        self.assertIn("+        초기화", result["template_diff"][0]["diff"])
        self.assertEqual(["src/App.tsx"], [r["file"] for r in result["mine_diff"]])
        self.assertIn("초기화", result["mine_diff"][0]["diff"])
        self.assertEqual("x01-F", result["followups"])
        self.assertEqual(["c1", "c2", "c3", "m1", "m2"], [i["key"] for i in result["self_items"]])
        self.assertEqual(["끝", "통과", "잠김"], [s["label"] for s in result["steps"]])
        self.assertEqual(["l90"], result["pages"])
        again = web.finish("x01")  # 끝난 미션은 기록 없이 같은 것
        self.assertEqual(len(self.log()), len(self.log()))
        self.assertEqual(result["explain"], again["explain"])
        self.solve(2)
        self.assertEqual([], web.finish("x01")["mine_diff"])
        ticks = web.self_check("x01", {"c1": 1, "c2": 0, "m1": True})
        self.assertEqual({"c1": 1, "c2": 0, "m1": 1}, ticks)
        self.assertEqual("self", self.kinds()[-1])
        self.assertEqual(ticks, web.finish("x01")["self_ticks"])

    def test_finish_before_live_is_refused(self):
        web = self.session()
        with self.assertRaises(WebError):
            web.finish("x01")
        web.get("x01")
        with self.assertRaises(WebError):
            web.finish("x01")
        with self.assertRaises(WebError):
            web.self_check("x01", {"c1": 1})

    def test_hidden_checks_run_at_finish(self):
        root = os.path.join(self.tmp, "hidden_bank")
        shutil.copytree(FIXTURE, root)
        meta_path = os.path.join(root, "missions", "x01", "meta.json")
        meta = study.read_json(meta_path)
        meta["hidden"] = True
        study.write_text(meta_path, json.dumps(meta))
        study.write_text(os.path.join(root, "missions", "x01", "work", "checks", "hidden.test.tsx"),
                         "import { test } from 'vitest';\ntest('h1 숨긴 검사가 통과합니다', () => {});\n")
        with mock.patch.object(bank, "BANK_DIR", root):
            web = self.to_live(self.session())
            self.tick(minutes=3)
            web.skip("x01")
            self.tick(minutes=3)
            web.skip("x01")
        self.assertEqual({"pass": ["h1"], "fail": []}, self.log()[-1]["hidden"])
        self.assertEqual("finish", self.log()[-1]["kind"])

    def test_hidden_checks_without_stack_leave_no_terminal_command(self):
        """끝낼 때 검사 도구가 없어 숨긴 검사를 못 돌리면 그 까닭을 기록함. 화면의 해설 탭에도 보이므로 설치 명령을 담지 않음."""
        root = os.path.join(self.tmp, "hidden_bank")
        shutil.copytree(FIXTURE, root)
        meta_path = os.path.join(root, "missions", "x01", "meta.json")
        study.write_text(meta_path, json.dumps(dict(study.read_json(meta_path), hidden=True)))
        study.write_text(os.path.join(root, "missions", "x01", "work", "checks", "hidden.test.tsx"),
                         "import { test } from 'vitest';\ntest('h1 숨긴 검사가 통과합니다', () => {});\n")
        with mock.patch.object(bank, "BANK_DIR", root):
            web = self.to_live(self.session())
            os.remove(os.path.join(self.repo, stack.VITEST_MJS))
            done = web.finish("x01")
        self.assertEqual({"error": service.HIDDEN_NO_STACK}, self.log()[-1]["hidden"])
        self.assertEqual({"error": service.HIDDEN_NO_STACK}, done["hidden"])
        self.assertNotIn("study.py", service.HIDDEN_NO_STACK)

    def test_check_without_stack_or_node_explains(self):
        web = self.to_live(self.session())
        os.remove(os.path.join(self.repo, stack.VITEST_MJS))
        with self.assertRaises(WebError) as caught:
            web.check("x01")
        self.assertIn("web install", str(caught.exception))
        self.node = None
        with self.assertRaises(WebError) as caught:
            web.check("x01")
        self.assertIn("Node.js 22.12", str(caught.exception))
        self.assertEqual(["receive", "live", "step"], self.kinds())

    def test_check_error_from_vitest_is_a_web_error(self):
        web = self.to_live(self.session())
        with mock.patch.object(checks, "_popen", side_effect=OSError("no node")):
            with self.assertRaises(WebError) as caught:
                web.check("x01")
        self.assertIn("no node", str(caught.exception))
        self.assertFalse(os.path.exists(os.path.join(self.repo, ".web-check")))


class StackServiceTest(Base):
    def test_consent_and_state(self):
        web = self.session()
        self.assertIn("약 80MB", web.consent())
        state = web.stack_state()
        self.assertEqual((True, False, ""), (state["installed"], state["stale"], state["problem"]))
        self.assertEqual("22.23.2", state["node"]["version"])

    def test_install_uses_stack_and_fails_without_node(self):
        with mock.patch.object(stack, "install", return_value={"ok": True, "message": "설치했습니다.", "seconds": 1.0, "log": "x"}) as fake:
            result = self.session().install()
        self.assertEqual("설치했습니다.", result["message"])
        self.assertEqual((self.repo, FAKE_NODE), fake.call_args[0][:2])
        with mock.patch.object(stack, "install", return_value={"ok": False, "message": "실패", "seconds": 1.0, "log": "x"}):
            with self.assertRaises(WebError):
                self.session().install()
        self.node = None
        with self.assertRaises(WebError):
            self.session().install()

    def test_uninstall(self):
        removed = self.session().uninstall()["removed"]
        self.assertEqual([os.path.join(self.repo, "node_modules")], removed)
        self.assertIn("web install", self.session().stack_state()["problem"])


class LearnTest(Base):
    def test_show_records_learn(self):
        web = self.session()
        page = web.show("l90")
        self.assertIn("[그림] 그림 1.", page["text"])
        self.assertIn("```figure", page["markdown"])
        self.assertEqual({"kind": "learn", "page": "l90"}, {k: self.log()[-1][k] for k in ("kind", "page")})
        with self.assertRaises(WebError):
            web.show("l91")
        with self.assertRaises(WebError):
            web.show("l99")


class DrillTest(Base):
    def test_chain_view(self):
        web = self.session()
        chain = web.chain("90-A")
        self.assertEqual(("버튼을 눌렀는데 화면이 그대로일 때", 60, "l90", "90a", None, 0), (chain["title"], chain["secs"], chain["page"],
                                                                                chain["section"], chain["box"], chain["times"]))
        self.assertEqual([1, 2, 3], [q["no"] for q in chain["questions"]])
        self.assertIsNone(chain["questions"][0]["last"])
        self.assertTrue(chain["code"].startswith("```tsx"))
        self.to_live(web).finish("x01")  # 미션 꼬리 질문은 끝낸 뒤에만 풀림
        follow = web.chain("x01-F")
        self.assertEqual("x01", follow["mission"])
        self.assertEqual(2, len(follow["questions"]))
        with self.assertRaises(WebError):
            web.chain("9-Z")

    def test_answers_and_chain_result_schedule_review(self):
        web = self.session()
        answer = web.answer("90-A", 1, 48, [1], [1], None, "일반 변수는 React 가 모름")
        self.assertEqual(("pass", ""), (answer["result"], answer["stuck"]))
        entry = self.log()[-1]
        self.assertEqual({"kind": "drill", "chain": "90-A", "q": 1, "secs": 48, "need": [1], "extra": [1], "talked": None,
                          "note": "일반 변수는 React 가 모름"}, {k: entry[k] for k in entry if k != "at"})
        answer = web.answer("90-A", 2, 70, [0], [], True)
        self.assertEqual("stuck", answer["result"])
        self.assertIn("다시 그려 달라", answer["stuck"])
        self.assertEqual(1, self.log()[-1]["talked"])
        web.answer("90-A", 3, 20, [1], [0], None)
        done = web.finish_chain("90-A")
        self.assertEqual(("stuck", ["pass", "stuck", "pass"], 1, "2026-10-22"), (done["result"], done["per_question"], done["box"], done["due"]))
        self.assertEqual('"리렌더링이 안 돼서 그렇습니다."', done["weak"]["quote"])
        self.assertTrue(done["follow"].startswith('"count 는'))
        self.assertEqual(("l90", "90a"), (done["page"], done["section"]))
        self.assertEqual({"kind": "chain", "chain": "90-A", "result": "stuck"}, {k: self.log()[-1][k] for k in ("kind", "chain", "result")})
        chain = web.chain("90-A")
        self.assertEqual((1, "2026-10-22", 1), (chain["box"], chain["due"], chain["times"]))
        self.assertEqual("일반 변수는 React 가 모름", chain["questions"][0]["last"]["note"])
        self.assertEqual([0], chain["questions"][1]["last"]["need"])
        # 다음 날 통과하면 상자 2, 3일 뒤
        self.clock = "2026-10-22T10:00:00"
        for q in (1, 2, 3):
            web.answer("90-A", q, 30, [1], [1])
        done = web.finish_chain("90-A")
        self.assertEqual(("pass", 2, "2026-10-25"), (done["result"], done["box"], done["due"]))

    def test_marks_are_padded_and_unknown_question_is_an_error(self):
        web = self.to_live(self.session())
        web.finish("x01")
        web.answer("x01-F", 2, 10, [1], [])  # Q2 는 [필수] 둘
        self.assertEqual([1, 0], self.log()[-1]["need"])
        web.answer("x01-F", 1, 10, [1, 1, 1], [1, 1, 1])
        self.assertEqual(([1], [1]), (self.log()[-1]["need"], self.log()[-1]["extra"]))
        with self.assertRaises(WebError):
            web.answer("x01-F", 5, 10, [1], [])
        done = web.finish_chain("x01-F")
        self.assertEqual(("partial", ["pass", "partial"]), (done["result"], done["per_question"]))

    def test_unanswered_questions_count_as_stuck(self):
        web = self.session()
        web.answer("90-B", 1, 10, [1], [])
        done = web.finish_chain("90-B")
        self.assertEqual(("stuck", ["pass", "stuck"]), (done["result"], done["per_question"]))

    def test_local_topic_records_go_to_home(self):
        root = os.path.join(self.tmp, "local_bank")
        shutil.copytree(FIXTURE, root)
        meta_path = os.path.join(root, "drills", "t90", "meta.json")
        meta = study.read_json(meta_path)
        meta["local"] = True
        study.write_text(meta_path, json.dumps(meta, ensure_ascii=False))
        with mock.patch.object(bank, "BANK_DIR", root):
            web = self.session()
            web.answer("90-A", 1, 10, [1], [])
            web.finish_chain("90-A")
            self.assertEqual([], self.log())
            local = study.read_json(os.path.join(self.home, "record.json"))["log"]
            self.assertEqual(["drill", "chain"], [e["kind"] for e in local])
            self.assertEqual(1, web.chain("90-A")["box"])
            self.assertEqual(["90-B"], [r["chain"] for r in web.today_list(datetime.date(2026, 10, 21))["chains"]])


class TodayOverviewTest(Base):
    def test_today_list_mixes_due_and_new_chains(self):
        web = self.session()
        today = web.today_list()
        self.assertEqual(["90-A", "90-B"], [r["chain"] for r in today["chains"]])
        self.assertTrue(all(r["new"] for r in today["chains"]))
        self.assertEqual([], today["missions"])
        self.assertEqual(8, today["minutes"])
        study.write_text(os.path.join(self.home, "settings.json"), '{"new_per_day": 1}')
        self.assertEqual(["90-A"], [r["chain"] for r in web.today_list()["chains"]])
        web.answer("90-B", 1, 10, [1], [])
        web.finish_chain("90-B")
        today = web.today_list(datetime.date(2026, 10, 21))
        self.assertEqual(["90-A"], [r["chain"] for r in today["chains"]])
        today = web.today_list(datetime.date(2026, 10, 30))
        self.assertEqual(["90-B", "90-A"], [r["chain"] for r in today["chains"]])
        self.assertEqual([False, True], [r["new"] for r in today["chains"]])

    def test_next_takes_a_running_mission_then_a_due_review_then_the_order(self):
        """이어서 할 일: 읽는 중·실전 중 미션, 한 번 푼 사슬의 오늘 복습, 권장 순서 차례. 새 사슬은 복습으로 치지 않음."""
        web = self.session()
        web.answer("90-B", 1, 10, [1], [])
        web.finish_chain("90-B")

        def next_on(day):
            with mock.patch.object(service, "today", lambda: day):
                target = web.overview()["next"]
            return target["kind"], target["id"]

        self.assertEqual(("page", "l90"), next_on(datetime.date(2026, 10, 21)))  # 복습 날이 아니면 권장 순서(새 사슬 90-A 는 건너뜀)
        self.assertEqual(("chain", "90-B"), next_on(datetime.date(2026, 10, 30)))  # 복습할 사슬이 권장 순서보다 먼저
        web.get("x01")
        self.assertEqual(("mission", "x01"), next_on(datetime.date(2026, 10, 30)))  # 읽는 중인 미션이 가장 먼저

    def test_mission_followup_chain_is_new_only_after_finish(self):
        web = self.to_live(self.session())
        study.write_text(os.path.join(self.home, "settings.json"), '{"new_per_day": 5}')
        self.assertNotIn("x01-F", [r["chain"] for r in web.today_list()["chains"]])
        web.finish("x01")
        self.assertEqual(["x01-F", "90-A", "90-B"], [r["chain"] for r in web.today_list()["chains"]])  # index.order 순서

    def test_mission_followup_chain_waits_for_finish(self):
        web = self.to_live(self.session())
        for call in (lambda: web.chain("x01-F"), lambda: web.answer("x01-F", 1, 10, [1], []), lambda: web.finish_chain("x01-F")):
            with self.assertRaises(WebError) as caught:
                call()
            self.assertIn("미션을 끝낸 뒤에", str(caught.exception))
        self.assertEqual([], [e for e in self.log() if e["kind"] in ("drill", "chain")])
        web.finish("x01")
        self.assertEqual("x01", web.chain("x01-F")["mission"])
        # 복습 날짜가 잡힌 뒤 미션을 다시 받으면 끝낼 때까지 오늘 복습에서도 빠짐
        for q in (1, 2):
            web.answer("x01-F", q, 10, [1, 1], [1])
        web.finish_chain("x01-F")
        later = datetime.date(2026, 11, 1)  # 통과한 사슬의 다음 복습 날짜도 지난 뒤
        self.assertIn("x01-F", [r["chain"] for r in web.today_list(later)["chains"]])
        web.get("x01", again=True)
        self.assertNotIn("x01-F", [r["chain"] for r in web.today_list(later)["chains"]])

    def test_retry_mission_appears_after_seven_days(self):
        web = self.to_live(self.session())
        self.tick(minutes=3)
        web.skip("x01")
        web.finish("x01")
        self.assertEqual([], web.today_list(datetime.date(2026, 10, 27))["missions"])
        rows = web.today_list(datetime.date(2026, 10, 28))["missions"]
        self.assertEqual([("x01", "넘어간 단계가 있습니다")], [(r["mission"], r["why"]) for r in rows])

    def test_overview(self):
        web = self.session()
        view = web.overview()
        self.assertTrue(view["stack"]["installed"])
        self.assertEqual([("x01", True, "none"), ("x02", False, "none")], [(m["id"], m["ready"], m["phase"]) for m in view["missions"]])
        self.assertEqual((1, 0), (view["ready_missions"], view["done_missions"]))
        self.assertEqual([("t90", True, 0, 2), ("t91", False, 0, 0)], [(t["id"], t["ready"], t["done"], t["total"]) for t in view["topics"]])
        self.assertEqual([None, None], [c["box"] for c in view["topics"][0]["chains"]])
        self.assertEqual([("l90", True, None), ("l91", False, None)], [(p["id"], p["ready"], p["learned_at"]) for p in view["pages"]])
        self.assertEqual({"kind": "page", "id": "l90", "title": web.pages["l90"]["title"]}, view["next"])
        self.assertEqual((0, 0), (view["talked"], view["stuck"]))
        web.show("l90")
        self.assertEqual("mission", web.overview()["next"]["kind"])
        self.to_live(web)
        self.solve(2)
        web.check("x01")
        web.check("x01")
        view = web.overview()
        self.assertEqual(("done", 2, 3), (view["missions"][0]["phase"], view["missions"][0]["done_steps"], view["missions"][0]["total_steps"]))  # 0단계는 세지 않음
        self.assertEqual("topic", view["next"]["kind"])
        self.assertEqual([self.clock[:10]], view["activity"])
        web.answer("90-A", 1, 10, [0], [], False)
        self.assertEqual((0, 1), (web.overview()["talked"], web.overview()["stuck"]))


@unittest.skipUnless(REAL_NODE and HAS_STACK, "저장소 맨 위 node_modules 와 Node 22.12 이상이 있어야 함")
class RealVitestTest(Base):
    """실제 vitest·jsdom 으로 고정 은행 x01 을 돌림. 템플릿은 1단계에서 떨어지고, step1 답은 1단계만, step2 답은 모두 통과함."""

    def setUp(self):
        super().setUp()
        for patcher in (mock.patch.object(checks, "_popen", checks.subprocess.Popen),
                        mock.patch.object(stack, "find_node", lambda saved=None, probe=False: REAL_NODE)):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_template_and_solutions(self):
        web = self.to_live(self.session(repo=ROOT))
        result = web.check("x01")
        self.assertEqual((False, ["1a", "1b"]), (result["passed"], result["fail"]))
        self.assertIn('이름이 "더하기"인 버튼이 있습니다', result["tests"][0]["title"], result["tests"][0]["message"])
        self.assertEqual('이름이 "더하기"이고 역할(role)이 button인 요소를 화면에서 찾지 못했습니다.', result["tests"][0]["message"])
        self.assertIn("Unable to find an accessible element", result["tests"][0]["detail"].splitlines()[0])  # 영어 원문은 접어 둠
        self.assertIn("<body>", result["tests"][0]["detail"])
        self.solve(1)
        result = web.check("x01")
        self.assertTrue(result["passed"])
        result = web.check("x01")
        self.assertEqual((2, False, ["2a"]), (result["open"], result["passed"], result["fail"]))
        self.solve(2)
        result = web.check("x01")
        self.assertEqual((True, True, []), (result["passed"], result["finished"], result["fail"]))
        self.assertFalse(os.path.exists(os.path.join(ROOT, ".web-check")))


if __name__ == "__main__":
    unittest.main()
