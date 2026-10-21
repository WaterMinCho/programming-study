# -*- coding: utf-8 -*-
"""웹 면접 준비 은행·봉인·Node 최소 판·설치·검사 모듈 테스트. 고정 은행 tests/web_bank(미션 x01 두 단계, 주제 t90 사슬 둘,
학습 페이지 l90, 준비 중 x02·t91·l91)을 읽고, 설치와 vitest 는 가짜 subprocess 로 흉내 냄. Node 가 없어도 모두 돎.

실행: python -m unittest tests.test_web_bank
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("STUDY_NODE_PROBE", "0")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import study  # noqa: E402
from journey import node  # noqa: E402
from webprep import bank, checks, stack  # noqa: E402

FIXTURE = os.path.join(ROOT, "tests", "web_bank")
MISSION_DIR = os.path.join(FIXTURE, "missions", "x01")

# vitest 4.0.18 JSON 보고서의 실제 모양을 줄인 것(2026-10-21 실행 사본). 색 코드와 DOM 덤프가 실패 문구에 섞여 옴
REPORT = {
    "numTotalTests": 3, "numPassedTests": 1, "numFailedTests": 2, "success": False, "startTime": 1792510572089,
    "testResults": [
        {"startTime": 1792510572446, "endTime": 1792510572535, "status": "failed", "message": "",
         "name": "/repo/.web-check/x01/checks/step1.test.tsx",
         "assertionResults": [
             {"ancestorTitles": [], "fullName": "1a 이름이 \"더하기\"인 버튼이 있습니다", "status": "passed",
              "title": "1a 이름이 \"더하기\"인 버튼이 있습니다", "duration": 75.9, "failureMessages": []},
             {"ancestorTitles": [], "fullName": "1b 더하기 버튼을 두 번 누르면 \"지금까지 2번\"이 보입니다", "status": "failed",
              "title": "1b 더하기 버튼을 두 번 누르면 \"지금까지 2번\"이 보입니다", "duration": 12.3,
              "failureMessages": ["TestingLibraryElementError: Unable to find an element with the text: 지금까지 2번\n\n"
                                  "Ignored nodes: comments, script, style\n\u001b[36m<body>\u001b[39m\n  \u001b[36m<div>\u001b[39m\n"
                                  "    \u001b[0m지금까지 1번\u001b[0m\n\u001b[36m</body>\u001b[39m"]}]},
        {"startTime": 1792510602322, "endTime": 1792510602322, "status": "failed",
         "message": "Transform failed with 1 error:\n/repo/.web-check/x01/checks/step2.test.tsx:9:2: ERROR: Expected \")\" but found \"expect\"",
         "name": "/repo/.web-check/x01/checks/step2.test.tsx", "assertionResults": []},
    ],
}


class FakeRun(object):
    """subprocess.run 자리. 부른 명령을 남기고 returncode 를 돌려줌. stdout 핸들이 있으면 글을 써 줌."""

    def __init__(self, returncode=0, text="added 156 packages\n", raise_timeout=False, on_run=None):
        self.calls = []
        self.returncode = returncode
        self.text = text
        self.raise_timeout = raise_timeout
        self.on_run = on_run

    def __call__(self, args, **options):
        self.calls.append((list(args), options))
        if self.raise_timeout:
            raise subprocess.TimeoutExpired(args, options.get("timeout"))
        handle = options.get("stdout")
        if hasattr(handle, "write"):
            handle.write(self.text)
        if self.on_run:
            self.on_run(args, options)
        return mock.Mock(returncode=self.returncode, stdout=b"")


def sealed_copy(tmp):
    """고정 은행 사본에서 x01·t90 의 work/ 를 sealed.json 으로 묶고 평문을 지움."""
    root = os.path.join(tmp, "bank")
    shutil.copytree(FIXTURE, root)
    for folder in (os.path.join(root, "missions", "x01"), os.path.join(root, "drills", "t90")):
        files = bank.load_secrets(folder)
        study.write_text(os.path.join(folder, bank.SEALED_NAME), bank.seal_text(files, "시험용 봉인"))
        shutil.rmtree(os.path.join(folder, bank.WORK_DIR))
    return root


class IndexTest(unittest.TestCase):
    def test_index_lists_missions_topics_pages_and_order(self):
        index = bank.read_index(FIXTURE)
        self.assertEqual(["x01", "x02"], [m["id"] for m in index["missions"]])
        self.assertEqual({"id": "x01", "no": 1, "title": "횟수 세기 버튼", "level": "워밍업"}, index["missions"][0])
        self.assertEqual(["t90", "t91"], [t["id"] for t in index["topics"]])
        self.assertEqual(["l90", "l91"], [p["id"] for p in index["pages"]])
        self.assertEqual(["l90", "x01", "t90", "x02", "t91", "l91"], index["order"])

    def test_ready_means_meta_json_exists(self):
        self.assertTrue(bank.is_ready("mission", "x01", FIXTURE))
        self.assertFalse(bank.is_ready("mission", "x02", FIXTURE))
        self.assertTrue(bank.is_ready("topic", "t90", FIXTURE))
        self.assertFalse(bank.is_ready("topic", "t91", FIXTURE))
        self.assertTrue(bank.is_ready("page", "l90", FIXTURE))
        self.assertFalse(bank.is_ready("page", "l91", FIXTURE))

    def test_bad_index_is_a_bank_error(self):
        tmp = tempfile.mkdtemp(prefix="web_bank_")
        self.addCleanup(shutil.rmtree, tmp, True)
        study.write_text(os.path.join(tmp, "index.json"), '{"format": 1, "missions": [{"id": "../x"}]}')
        with self.assertRaises(bank.BankError):
            bank.read_index(tmp)
        study.write_text(os.path.join(tmp, "index.json"), "{broken")
        with self.assertRaises(bank.BankError):
            bank.read_index(tmp)

    def test_terms(self):
        terms = bank.read_terms(FIXTURE)
        self.assertIn("useState", terms["known"])
        self.assertEqual({"term": "렌더링", "also": [], "page": "l90"}, terms["terms"][0])
        self.assertEqual({"known": [], "terms": []}, bank.read_terms(tempfile.gettempdir()))


class MissionTest(unittest.TestCase):
    def setUp(self):
        self.mission = bank.load_mission(bank.read_index(FIXTURE)["missions"][0], FIXTURE)
        self.secrets = bank.load_secrets(self.mission["dir"])

    def test_meta_fields(self):
        m = self.mission
        self.assertEqual(([1, 2, 2], 2, 6, False), (m["steps"], m["prep_min"], m["live_min"], m["hidden"]))
        self.assertEqual(["l90"], m["pages"])
        self.assertEqual(["90-A"], m["chains"])
        self.assertTrue(m["brief"].startswith("# x01."))
        self.assertTrue(os.path.isfile(os.path.join(m["app_dir"], "src", "App.tsx")))

    def test_bad_meta_is_a_bank_error(self):
        tmp = tempfile.mkdtemp(prefix="web_bank_")
        self.addCleanup(shutil.rmtree, tmp, True)
        root = os.path.join(tmp, "bank")
        shutil.copytree(FIXTURE, root)
        meta = os.path.join(root, "missions", "x01", "meta.json")
        data = study.read_json(meta)
        data["steps"] = []
        study.write_text(meta, json.dumps(data))
        with self.assertRaises(bank.BankError):
            bank.load_mission(bank.read_index(root)["missions"][0], root)
        data["steps"] = [1, 2]
        study.write_text(meta, json.dumps(data))
        shutil.rmtree(os.path.join(root, "missions", "x01", "app"))
        with self.assertRaises(bank.BankError) as caught:
            bank.load_mission(bank.read_index(root)["missions"][0], root)
        self.assertIn("app/", str(caught.exception))

    def test_secret_paths_are_relative_to_work(self):
        self.assertEqual(["check.md", "checks/step1.test.tsx", "checks/step2.test.tsx", "explain.md", "followups.md",
                          "solution/step1/src/App.tsx", "solution/step2/src/App.tsx", "steps.md"],
                         bank.plain_secret_paths(self.mission["dir"]))
        self.assertEqual(sorted(bank.plain_secret_paths(self.mission["dir"])), sorted(self.secrets))

    def test_parse_steps(self):
        steps = bank.parse_steps(self.secrets["steps.md"])
        self.assertEqual([0, 1, 2], [s["no"] for s in steps])
        self.assertEqual(["코드 설명", "더하기 버튼", "초기화 버튼"], [s["title"] for s in steps])
        self.assertTrue(steps[0]["request"].startswith("면접관: 받은 코드를"))
        self.assertEqual(2, len(steps[0]["self"]))
        self.assertEqual([], steps[0]["checks"])
        self.assertIn("접근성 이름", steps[1]["note"])
        self.assertEqual(2, len(steps[1]["checks"]))
        self.assertEqual(['"버튼 안의 글자가 그대로 접근성 이름이 됩니다."'], steps[1]["hints"])
        self.assertIsNone(steps[1]["after"])
        self.assertEqual(2, len(steps[2]["hints"]))
        self.assertTrue(steps[2]["after"]["ask"].startswith("면접관: 초기화 버튼"))
        self.assertEqual([True, False], [i["need"] for i in steps[2]["after"]["items"]])

    def test_check_files_ids_and_solutions(self):
        files = bank.check_files(self.secrets)
        self.assertEqual([1, 2], sorted(files))
        self.assertEqual(["1a", "1b"], bank.check_ids(files[1]))
        self.assertEqual(["2a"], bank.check_ids(files[2]))
        self.assertEqual(["3a"], bank.check_ids("test(\"3a 하나\", () => {});\nit('3a 둘', () => {});"))
        step1 = bank.solution_files(self.secrets, 1)
        self.assertEqual(["src/App.tsx"], list(step1))
        self.assertNotIn("초기화", step1["src/App.tsx"])
        self.assertIn("초기화", bank.solution_files(self.secrets, 2)["src/App.tsx"])

    def test_parse_followups_as_chain(self):
        chains = bank.parse_chains(self.secrets["followups.md"])
        self.assertEqual(["x01-F"], list(chains))
        chain = chains["x01-F"]
        self.assertEqual([1, 2], [q["no"] for q in chain["questions"]])
        self.assertEqual([True, False], [i["need"] for i in chain["questions"][0]["items"]])
        self.assertTrue(chain["questions"][0]["stuck"].startswith("`let count = 0`"))
        self.assertEqual('"React 에서는 원래 state 를 쓰니까요."', chain["weak"]["quote"])
        self.assertIn("관례라고만", chain["weak"]["why"])
        self.assertTrue(chain["follow"].startswith('"일반 변수는'))
        self.assertEqual(["버튼 이름을 글자로 바꿨고 속성을 따로 더하지 않았습니다.", "두 버튼이 같은 state 를 바꾼다고 말했습니다."],
                         bank.parse_bullets(self.secrets["check.md"]))


class TopicPageTest(unittest.TestCase):
    def test_topic_meta_and_chains(self):
        topic = bank.load_topic(bank.read_index(FIXTURE)["topics"][0], FIXTURE)
        self.assertEqual(["90-A", "90-B"], [c["id"] for c in topic["chains"]])
        self.assertEqual((60, ["x01"], "90a", "l90", False), (topic["chains"][0]["secs"], topic["chains"][0]["missions"],
                                                             topic["chains"][0]["section"], topic["page"], topic["local"]))
        chains = bank.parse_chains(bank.load_secrets(topic["dir"])["chains.md"])
        self.assertEqual(["90-A", "90-B"], list(chains))
        a = chains["90-A"]
        self.assertTrue(a["intro"].startswith("면접관이 버튼을"))
        self.assertTrue(a["code"].startswith("```tsx") and a["code"].endswith("```"))
        self.assertEqual(3, len(a["questions"]))
        self.assertEqual(["Q1", "Q2", "Q3"], ["Q%d" % q["no"] for q in a["questions"]])
        self.assertEqual("", chains["90-B"]["code"])
        self.assertEqual("", chains["90-B"]["follow"])
        self.assertIsNotNone(chains["90-B"]["weak"])

    def test_page(self):
        page = bank.load_page(bank.read_index(FIXTURE)["pages"][0], FIXTURE)
        self.assertEqual(["렌더링", "커밋"], page["defines"])
        self.assertEqual("일반 변수는 화면을 바꾸지 못합니다", page["sections"]["90a"])
        text = bank.strip_figures(page["markdown"])
        self.assertIn("[그림] 그림 1.", text)
        self.assertNotIn("assets/l90-1.png", text)
        self.assertNotIn("내용:", text)

    def test_kit_and_self_check(self):
        kit = bank.kit_files(FIXTURE)
        self.assertEqual(["render.tsx", "setup.ts"], sorted(kit))
        self.assertIn("jest-dom/vitest", kit["setup.ts"])
        self.assertEqual(3, len(bank.self_check(FIXTURE)))
        self.assertEqual({}, bank.kit_files(tempfile.gettempdir()))


class SealTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="web_bank_")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def test_sealed_only_reads_the_same_files(self):
        root = sealed_copy(self.tmp)
        mdir = os.path.join(root, "missions", "x01")
        self.assertFalse(os.path.isdir(os.path.join(mdir, "work")))
        self.assertEqual([], bank.plain_secret_paths(mdir))
        self.assertEqual(bank.load_secrets(MISSION_DIR), bank.load_secrets(mdir))
        self.assertEqual(bank.load_secrets(os.path.join(FIXTURE, "drills", "t90")), bank.load_secrets(os.path.join(root, "drills", "t90")))
        data = study.read_json(os.path.join(mdir, "sealed.json"))
        self.assertEqual("시험용 봉인", data["note"])
        self.assertEqual(bank.load_secrets(MISSION_DIR), study.unseal_blob(data["blob"]))

    def test_plain_work_file_wins_over_sealed(self):
        root = sealed_copy(self.tmp)
        mdir = os.path.join(root, "missions", "x01")
        study.write_text(os.path.join(mdir, "work", "explain.md"), "## 새 해설\n")
        files = bank.load_secrets(mdir)
        self.assertEqual("## 새 해설\n", files["explain.md"])
        self.assertIn("checks/step1.test.tsx", files)

    def test_broken_sealed_is_a_bank_error(self):
        root = sealed_copy(self.tmp)
        mdir = os.path.join(root, "missions", "x01")
        study.write_text(os.path.join(mdir, "sealed.json"), '{"blob": "not-base64!!"}')
        with self.assertRaises(bank.BankError):
            bank.load_secrets(mdir)
        study.write_text(os.path.join(mdir, "sealed.json"), json.dumps({"blob": study.seal_blob({"a": 1})}))
        with self.assertRaises(bank.BankError):
            bank.load_secrets(mdir)


class NodeMinimumTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="web_node_")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.addCleanup(node.forget)
        node.forget()
        self.node = os.path.join(self.tmp, "node")
        with open(self.node, "w") as f:
            f.write("")
        os.chmod(self.node, 0o755)

    def fake(self, version):
        def run(args, **options):
            return mock.Mock(stdout=("v%s\n" % version).encode(), returncode=0)
        return run

    def test_inspect_and_check_use_minimum(self):
        with mock.patch.object(node, "_run", self.fake("20.10.0")):
            self.assertTrue(node.inspect(self.node)["ok"])
            self.assertFalse(node.inspect(self.node, minimum=(22, 12))["ok"])
            self.assertEqual("20.10.0", node.check(self.node)["version"])
            with self.assertRaises(ValueError) as caught:
                node.check(self.node, minimum=(22, 12))
            self.assertIn("22.12", str(caught.exception))
        with mock.patch.object(node, "_run", self.fake("22.11.9")):
            self.assertFalse(node.inspect(self.node, minimum=(22, 12))["ok"])
        with mock.patch.object(node, "_run", self.fake("22.12.0")):
            self.assertTrue(node.inspect(self.node, minimum=(22, 12))["ok"])
        self.assertEqual("22.12", node.minimum_label((22, 12)))
        self.assertEqual("20", node.minimum_label(None))

    @unittest.skipIf(os.name == "nt", "PATH 에서는 node.exe 만 받아서 가짜 node 파일로는 Windows 에서 찾지 못함")
    def test_search_skips_candidates_below_minimum(self):
        env = {"PATH": self.tmp}
        with mock.patch.object(node, "MAC_FIXED", ()), mock.patch.object(node, "_run", self.fake("20.10.0")):
            self.assertEqual("20.10.0", node.search(env=env, home=self.tmp, platform="darwin")["version"])
            self.assertIsNone(node.search(env=env, home=self.tmp, platform="darwin", minimum=(22, 12)))

    def test_find_remembers_per_minimum(self):
        calls = []

        def fake_search(probe=False, saved=None, env=None, home=None, platform=None, minimum=None):
            calls.append(minimum)
            return None if minimum else {"path": "/x/node", "version": "20.10.0", "major": 20}

        with mock.patch.object(node, "search", fake_search):
            self.assertEqual("/x/node", node.find()["path"])
            self.assertIsNone(node.find(minimum=(22, 12)))
            self.assertIsNone(node.find(minimum=(22, 12)))
            self.assertEqual("/x/node", node.find()["path"])
            self.assertEqual([None, (22, 12)], calls)
            self.assertTrue(node.searched() and node.searched((22, 12)))
            node.remember({"path": "/y/node", "version": "22.23.2", "major": 22}, minimum=(22, 12))
            self.assertEqual("/y/node", node.find(minimum=(22, 12))["path"])
            self.assertEqual("/x/node", node.find()["path"])
            node.forget()
            self.assertFalse(node.searched() or node.searched((22, 12)))


class StackTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="web_stack_")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.repo = os.path.join(self.tmp, "repo")
        os.makedirs(self.repo)
        shutil.copyfile(os.path.join(ROOT, "package-lock.json"), os.path.join(self.repo, "package-lock.json"))
        self.home = os.path.join(self.tmp, "home")
        patch = mock.patch.dict(os.environ, {"STUDY_WEB_HOME": self.home})
        patch.start()
        self.addCleanup(patch.stop)
        bindir = os.path.join(self.tmp, "nodehome", "bin")
        os.makedirs(bindir)
        self.node_path = os.path.join(bindir, "node")
        with open(self.node_path, "w") as f:
            f.write("")
        self.cli = os.path.join(self.tmp, "nodehome", "lib", "node_modules", "npm", "bin", "npm-cli.js")
        study.write_text(self.cli, "")
        self.node = {"path": self.node_path, "version": "22.23.2", "major": 22}

    def install_files(self, root=None):
        root = root or self.repo
        study.write_text(os.path.join(root, stack.VITEST_MJS), "")

    def test_npm_cli_next_to_node(self):
        self.assertEqual(os.path.normpath(self.cli), stack.npm_cli(self.node_path))
        self.assertIsNone(stack.npm_cli(os.path.join(self.tmp, "nowhere", "node")))
        with mock.patch.object(stack.sys, "platform", "win32"):
            exe = os.path.join(self.tmp, "win", "node.exe")
            win_cli = os.path.join(self.tmp, "win", "node_modules", "npm", "bin", "npm-cli.js")
            study.write_text(win_cli, "")
            self.assertEqual(os.path.normpath(win_cli), stack.npm_cli(exe))

    def test_state_before_and_after_install(self):
        before = stack.state(self.repo, self.node)
        self.assertFalse(before["installed"])
        self.assertIn("web install", before["problem"])
        self.assertIn("Node.js 22.12", stack.state(self.repo, None)["problem"])
        self.install_files()
        unmarked = stack.state(self.repo, self.node)  # 손으로 npm install 한 경우: 설치는 됐지만 표시 파일이 없음
        self.assertEqual((True, True, True), (unmarked["installed"], unmarked["stale"], unmarked["no_marker"]))
        self.assertIn("설치 표시가 없습니다", unmarked["problem"])
        study.write_text(stack.marker_path(self.repo), stack.lock_hash(self.repo) + "\n")
        after = stack.state(self.repo, self.node)
        self.assertEqual((True, False, False, ""), (after["installed"], after["stale"], after["no_marker"], after["problem"]))
        study.write_text(os.path.join(self.repo, "package-lock.json"), "{}")
        stale = stack.state(self.repo, self.node)
        self.assertEqual((True, False), (stale["stale"], stale["no_marker"]))
        self.assertIn("패키지 목록이 바뀌었습니다. `python study.py web install`", stale["problem"])
        os.remove(os.path.join(self.repo, "package-lock.json"))
        self.assertIn("package-lock.json 을 찾지 못했습니다", stack.state(self.repo, self.node)["problem"])

    def test_consent_text(self):
        text = stack.consent_text(self.repo, self.node)
        self.assertIn("약 80MB", text)
        self.assertIn(os.path.join(self.repo, "node_modules"), text)
        self.assertIn("처음 설치할 때 한 번", text)
        self.assertIn("web uninstall", text)
        self.assertIn("22.23.2", text)
        self.assertNotIn("OneDrive", text)
        onedrive = os.path.join(self.tmp, "OneDrive", "repo")
        self.assertIn("OneDrive", stack.consent_text(onedrive, None))

    def test_install_runs_npm_cli_ci_and_writes_marker_and_log(self):
        fake = FakeRun(on_run=lambda args, options: self.install_files())
        said = []
        with mock.patch.object(stack, "_run", fake):
            result = stack.install(self.repo, self.node, report=said.append)
        self.assertTrue(result["ok"], result)
        args, options = fake.calls[0]
        self.assertEqual([self.node_path, os.path.normpath(self.cli), "ci", "--no-audit", "--no-fund", "--prefer-offline", "--ignore-scripts"], args)
        self.assertEqual(self.repo, options["cwd"])
        self.assertEqual(stack.INSTALL_LIMIT_S, options["timeout"])
        self.assertEqual(study.NO_WINDOW, options["creationflags"])
        self.assertEqual(subprocess.DEVNULL, options["stdin"])
        self.assertNotIn("NODE_OPTIONS", options["env"])
        self.assertEqual("1", options["env"]["CI"])
        self.assertEqual(stack.lock_hash(self.repo), stack.read_marker(self.repo))
        self.assertEqual(os.path.join(self.home, "install.log"), result["log"])
        log = study.read_text(result["log"])
        self.assertIn("npm-cli.js ci", log)
        self.assertIn("added 156 packages", log)
        self.assertEqual(1, len(said))
        self.assertFalse(stack.state(self.repo, self.node)["stale"])

    def test_install_failures_explain_with_log_path(self):
        with mock.patch.object(stack, "_run", FakeRun(returncode=1, text="npm ERR! network\n")):
            result = stack.install(self.repo, self.node)
        self.assertFalse(result["ok"])
        self.assertIn("종료 코드 1", result["message"])
        self.assertIn(result["log"], result["message"])
        with mock.patch.object(stack, "_run", FakeRun(raise_timeout=True)):
            result = stack.install(self.repo, self.node)
        self.assertIn("10분", result["message"])
        with mock.patch.object(stack, "_run", FakeRun()):  # 끝났지만 vitest.mjs 가 없음
            result = stack.install(self.repo, self.node)
        self.assertIn("vitest.mjs", result["message"])
        result = stack.install(self.repo, {"path": os.path.join(self.tmp, "lonely", "node"), "version": "22.23.2", "major": 22})
        self.assertIn("npm-cli.js", result["message"])

    def test_uninstall_removes_node_modules_and_check_dir(self):
        self.install_files()
        os.makedirs(os.path.join(self.repo, ".web-check", "x01"))
        removed = stack.uninstall(self.repo)["removed"]
        self.assertEqual(2, len(removed))
        self.assertFalse(os.path.exists(os.path.join(self.repo, "node_modules")))
        self.assertEqual([], stack.uninstall(self.repo)["removed"])


class ChecksTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="web_checks_")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.repo = os.path.join(self.tmp, "repo")
        study.write_text(os.path.join(self.repo, stack.VITEST_MJS), "")
        self.mission = bank.load_mission(bank.read_index(FIXTURE)["missions"][0], FIXTURE)
        self.secrets = bank.load_secrets(self.mission["dir"])
        self.kit = bank.kit_files(FIXTURE)
        self.app_src = os.path.join(self.mission["app_dir"], "src")

    def test_prepare_writes_checks_kit_setup_and_config(self):
        prepared = checks.prepare(self.repo, "x01", self.secrets, self.kit, [1, 2], self.app_src)
        folder = os.path.join(self.repo, ".web-check", "x01")
        self.assertEqual(folder, prepared["dir"])
        self.assertEqual({"1a": 1, "1b": 1, "2a": 2}, prepared["expected"])
        for rel in ("checks/step1.test.tsx", "checks/step2.test.tsx", "kit/render.tsx", "setup.ts", "vitest.config.mts"):
            self.assertTrue(os.path.isfile(os.path.join(folder, *rel.split("/"))), rel)
        self.assertFalse(os.path.exists(os.path.join(folder, "kit", "setup.ts")))
        config = study.read_text(prepared["config"])
        self.assertIn("root: %s" % json.dumps(self.repo.replace("\\", "/")), config)
        self.assertIn("'@app': %s" % json.dumps(self.app_src.replace("\\", "/")), config)
        self.assertIn('".web-check/x01/checks/step1.test.tsx"', config)
        self.assertIn('".web-check/x01/checks/step2.test.tsx"', config)
        self.assertIn("environment: 'jsdom'", config)
        self.assertIn("testTimeout: 5000", config)
        self.assertIn("setup.ts", config)
        checks.cleanup(self.repo, "x01")
        self.assertFalse(os.path.exists(os.path.join(self.repo, ".web-check")))

    def test_prepare_only_open_steps_and_missing_step_is_an_error(self):
        prepared = checks.prepare(self.repo, "x01", self.secrets, self.kit, [1], self.app_src)
        self.assertEqual({"1a": 1, "1b": 1}, prepared["expected"])
        self.assertFalse(os.path.exists(os.path.join(prepared["dir"], "checks", "step2.test.tsx")))
        with self.assertRaises(checks.CheckError):
            checks.prepare(self.repo, "x01", self.secrets, self.kit, [1, 3], self.app_src)

    def test_parse_report_reads_titles_status_and_cleans_messages(self):
        expected = {"1a": 1, "1b": 1, "2a": 2}
        parsed = checks.parse(json.dumps(REPORT), expected, "/repo")
        tests = {t["id"]: t for t in parsed["tests"]}
        self.assertEqual(["1a", "1b", "2a"], [t["id"] for t in parsed["tests"]])
        self.assertEqual(("pass", 75, '이름이 "더하기"인 버튼이 있습니다'), (tests["1a"]["status"], tests["1a"]["ms"], tests["1a"]["title"]))
        self.assertEqual("fail", tests["1b"]["status"])
        self.assertEqual("TestingLibraryElementError: Unable to find an element with the text: 지금까지 2번", tests["1b"]["message"])
        self.assertIn("<body>", tests["1b"]["detail"])
        self.assertNotIn("\u001b", tests["1b"]["detail"])
        self.assertEqual("fail", tests["2a"]["status"])
        self.assertIn("Transform failed", tests["2a"]["message"])
        self.assertIn("x01/checks/step2.test.tsx:9:2", tests["2a"]["message"])
        self.assertNotIn("/repo/.web-check/", tests["2a"]["message"])
        self.assertEqual(["step2.test.tsx"], parsed["file_errors"])
        with self.assertRaises(checks.CheckError):
            checks.parse("not json", expected, "/repo")

    def test_clean_message_clips_to_twelve_lines(self):
        shown, detail = checks.clean_message(["\n".join("줄 %d" % n for n in range(20))], "/repo")
        self.assertEqual(13, len(shown.splitlines()))
        self.assertTrue(shown.endswith("… (이하 생략)"))
        self.assertEqual("", detail)

    def test_run_steps_uses_fake_vitest_and_cleans_up(self):
        seen = {}

        class FakeProc(object):
            def __init__(self, cmd, **options):
                seen["cmd"], seen["options"] = cmd, options
                self.returncode = 1
                out = [a for a in cmd if a.startswith("--outputFile=")][0].split("=", 1)[1]
                seen["check_dir_existed"] = os.path.isdir(os.path.join(options["cwd"], ".web-check", "x01", "checks"))
                study.write_text(out, json.dumps(REPORT))

            def communicate(self, timeout=None):
                return b"", b""

        with mock.patch.object(checks, "_popen", FakeProc):
            result = checks.run_steps("/fake/node", self.repo, "x01", self.secrets, self.kit, [1, 2], self.app_src)
        cmd, options = seen["cmd"], seen["options"]
        self.assertEqual(["/fake/node", os.path.join(self.repo, "node_modules", "vitest", "vitest.mjs"), "run", "--config"], cmd[:4])
        self.assertIn("--reporter=json", cmd)
        self.assertEqual(self.repo, options["cwd"])
        self.assertEqual(study.NO_WINDOW, options["creationflags"])
        self.assertEqual(("1", "0"), (options["env"]["CI"], options["env"]["FORCE_COLOR"]))
        self.assertNotIn("NODE_OPTIONS", options["env"])
        self.assertTrue(seen["check_dir_existed"])
        self.assertEqual(["1a"], result["pass"])
        self.assertEqual(["1b", "2a"], result["fail"])
        self.assertEqual({1: {"pass": ["1a"], "fail": ["1b"], "ok": False}, 2: {"pass": [], "fail": ["2a"], "ok": False}}, result["by_step"])
        self.assertEqual([], result["warnings"])
        self.assertFalse(os.path.exists(os.path.join(self.repo, ".web-check")))

    def test_run_steps_timeout_kills_and_cleans_up(self):
        class HangingProc(object):
            def __init__(self, cmd, **options):
                self.pid = os.getpid() + 100000
                self.returncode = None
                self.killed = 0

            def communicate(self, timeout=None):
                if self.killed:
                    return b"", b""
                raise subprocess.TimeoutExpired("vitest", timeout)

            def kill(self):
                self.killed += 1

        with mock.patch.object(checks, "_popen", HangingProc), mock.patch.object(checks, "_kill_tree", lambda proc: proc.kill()):
            with self.assertRaises(checks.CheckError) as caught:
                checks.run_steps("/fake/node", self.repo, "x01", self.secrets, self.kit, [1], self.app_src, limit=1)
        self.assertIn("1초 안에 끝나지 않았습니다", str(caught.exception))
        self.assertFalse(os.path.exists(os.path.join(self.repo, ".web-check")))

    def test_run_steps_warns_about_node_modules_in_learner_folder(self):
        learner = os.path.join(self.tmp, "learner")
        shutil.copytree(self.mission["app_dir"], learner)
        os.makedirs(os.path.join(learner, "node_modules", ".vite", "vitest"))  # 미션 폴더에서 npm test 를 돌리면 생기는 캐시

        class FakeProc(object):
            def __init__(self, cmd, **options):
                self.returncode = 0
                out = [a for a in cmd if a.startswith("--outputFile=")][0].split("=", 1)[1]
                study.write_text(out, json.dumps({"testResults": []}))

            def communicate(self, timeout=None):
                return b"", b""

        with mock.patch.object(checks, "_popen", FakeProc):
            result = checks.run_steps("/fake/node", self.repo, "x01", self.secrets, self.kit, [1], os.path.join(learner, "src"))
        self.assertEqual([], result["warnings"])  # 점 항목뿐이면 경고하지 않음
        self.assertEqual(["1a", "1b"], result["fail"])  # 결과에 없는 검사는 실패로 적음
        os.makedirs(os.path.join(learner, "node_modules", "react"))
        with mock.patch.object(checks, "_popen", FakeProc):
            result = checks.run_steps("/fake/node", self.repo, "x01", self.secrets, self.kit, [1], os.path.join(learner, "src"))
        self.assertEqual(1, len(result["warnings"]))
        self.assertIn("node_modules", result["warnings"][0])

    def test_run_without_vitest_is_an_error(self):
        os.remove(os.path.join(self.repo, stack.VITEST_MJS))
        with self.assertRaises(checks.CheckError) as caught:
            checks.run("/fake/node", self.repo, "x.mts", "out.json")
        self.assertIn("web install", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
