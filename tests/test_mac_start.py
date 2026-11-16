"""Mac 실행기를 임시 폴더에서 검사함. 설치·화면·사용자 설정은 건드리지 않음."""
import os
from pathlib import Path
import select
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

import bootstrap

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.name == "posix", "POSIX 실행기 검사")
class MacStartTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="mac-start-")
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.repo = self.base / "한글 공부 폴더"
        self.repo.mkdir()
        self.bin = self.base / "bin"
        self.bin.mkdir()
        self.home = self.base / "home"
        self.home.mkdir()
        self.env = dict(os.environ, HOME=str(self.home), PATH=str(self.bin))
        self.env.pop("STUDY_WINDOW", None)
        self.env.pop("STUDY_VENV", None)
        self.script = self.repo / "start.command"
        script = (ROOT / "start.command").read_text()
        # OS 설치 경로도 임시 위치로 바꿔 실제 Python 후보를 실행하지 않음.
        for path in ("/Library/Frameworks/Python.framework", "/opt/homebrew", "/usr/local"):
            script = script.replace(path, str(self.base / path.lstrip("/")))
        self.script.write_text(script)
        self.script.chmod(0o755)
        (self.repo / "bootstrap.py").touch()
        (self.repo / "study.py").write_text("print('APP_STARTED')\n")
        os.symlink(shutil.which("dirname"), self.bin / "dirname")
        self.fake_python("python3")

    def fake_python(self, name, probe_ok=True, folder=None):
        path = (folder or self.bin) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        probe_status = 0 if probe_ok else 1
        path.write_text(
            '#!/bin/sh\nif [ "$1" = -c ]; then exit %d; fi\nexec %s "$@"\n'
            % (probe_status, shlex.quote(sys.executable)))
        path.chmod(0o755)
        return path

    def run_start(self, *args):
        return subprocess.run([str(self.script), *args], cwd=self.base, env=self.env,
                              input="", capture_output=True, text=True, timeout=10)

    def log(self):
        return (self.home / ".rokey-study" / "launch.log").read_text()

    def test_normal_exit_and_arguments_from_a_different_directory(self):
        (self.repo / "study.py").write_text("import os,sys\nprint(os.getcwd())\nprint(sys.argv[1:])\n")
        result = self.run_start("update")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(str(self.repo), result.stdout)
        self.assertIn("['update']", result.stdout)
        self.assertNotIn("Enter", result.stdout)
        self.assertIn("exit=0", self.log())

    def test_old_path_python_falls_back_to_python_org_install(self):
        self.fake_python("python3", probe_ok=False)
        python = self.fake_python("python3.14", folder=self.base / "Library/Frameworks/Python.framework/Versions/3.14/bin")
        result = self.run_start()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("APP_STARTED", result.stdout)
        self.assertIn("Python=" + str(python), self.log())

    def test_supported_path_python_is_kept(self):
        self.fake_python("python3.14")
        result = self.run_start()
        self.assertEqual(result.returncode, 0)
        self.assertIn("Python=" + str(self.bin / "python3") + "\n", self.log())

    def test_missing_and_unsupported_python_explain_installation(self):
        for exists in (True, False):
            with self.subTest(exists=exists):
                self.fake_python("python3", probe_ok=False)
                if not exists:
                    (self.bin / "python3").unlink()
                result = self.run_start()
                self.assertEqual(result.returncode, 1)
                self.assertIn("Python 3.10~3.14", result.stdout)
                self.assertIn("python.org", result.stdout)
                self.assertNotIn("APP_STARTED", result.stdout)

    def test_missing_project_file_explains_location(self):
        (self.repo / "study.py").unlink()
        result = self.run_start()
        self.assertEqual(result.returncode, 1)
        self.assertIn("프로그램 파일을 찾지 못했습니다", result.stdout)

    def test_failure_keeps_stderr_exit_code_and_appends_private_log(self):
        (self.repo / "study.py").write_text("import sys\nprint('IMPORT_FAILED', file=sys.stderr)\nsys.exit(37)\n")
        log = self.home / ".rokey-study" / "launch.log"
        log.parent.mkdir()
        log.write_text("previous failure\n")
        result = self.run_start()
        self.assertEqual(result.returncode, 37)
        self.assertIn("IMPORT_FAILED", result.stderr)
        self.assertIn("다시 실행: ./start.command", result.stdout)
        self.assertIn("previous failure", self.log())
        self.assertIn("exit=37", self.log())
        self.assertEqual(log.stat().st_mode & 0o777, 0o600)

    def test_updating_launcher_while_running_keeps_the_loaded_exit_handler(self):
        (self.repo / "study.py").write_text(
            "from pathlib import Path\nimport sys\n"
            "Path('start.command').write_text('BROKEN_NEW_SHELL_CONTENT\\n' * 300)\n"
            "sys.exit(19)\n")
        result = self.run_start()
        self.assertEqual(result.returncode, 19, result.stderr)
        self.assertIn("다시 실행: ./start.command", result.stdout)
        self.assertNotIn("BROKEN_NEW_SHELL_CONTENT", result.stderr)

    def test_interactive_install_input_and_failure_wait(self):
        import pty
        (self.repo / "study.py").write_text(
            "import sys\nassert sys.stdin.isatty()\n"
            "answer = input('INSTALL? ')\nprint('ANSWER=' + answer)\nsys.exit(23)\n")
        master, slave = pty.openpty()
        self.addCleanup(os.close, master)
        proc = subprocess.Popen([str(self.script)], cwd=self.base, env=self.env,
                                stdin=slave, stdout=slave, stderr=slave)
        os.close(slave)
        self.addCleanup(lambda: proc.poll() is None and proc.kill())
        output = b""

        def until(marker):
            nonlocal output
            deadline = time.monotonic() + 10
            while marker.encode() not in output:
                self.assertGreater(deadline - time.monotonic(), 0, output.decode(errors="replace"))
                ready, _, _ = select.select([master], [], [], max(0, deadline - time.monotonic()))
                self.assertTrue(ready, output.decode(errors="replace"))
                output += os.read(master, 8192)

        until("INSTALL?")
        os.write(master, b"y\n")
        until("Enter를 누르면 종료")
        self.assertIsNone(proc.poll())
        self.assertIn(b"ANSWER=y", output)
        os.write(master, b"\n")
        self.assertEqual(proc.wait(timeout=5), 23)

    def test_probe_agrees_with_bootstrap_version_and_bits(self):
        script = (ROOT / "start.command").read_text()
        probe = script.split("-c '", 1)[1].split("'", 1)[0]
        # 실제 실행기의 검사식을 여러 버전과 비트 수로 실행함.
        for version in ((3, 9), (3, 10), (3, 14), (3, 15)):
            for bits in (32, 64):
                source = "import sys\nsys.version_info=%r\nsys.maxsize=%d\n%s" % (version, 2 ** (bits - 1) - 1, probe)
                result = subprocess.run([sys.executable, "-c", source], capture_output=True, timeout=5)
                expected = bootstrap.python_problem({"version": version, "bits64": bits == 64, "platform": "macosx"})
                self.assertEqual(result.returncode == 0, expected is None, (version, bits))


if __name__ == "__main__":
    unittest.main()
