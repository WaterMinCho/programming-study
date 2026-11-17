"""Mac 실행기를 임시 폴더에서 검사함. 설치·화면·사용자 설정은 건드리지 않음."""
import errno
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
        (self.repo / "tools").mkdir()
        shutil.copyfile(ROOT / "tools/install_python_macos.sh", self.repo / "tools/install_python_macos.sh")
        (self.repo / "study.py").write_text("print('APP_STARTED')\n")
        os.symlink(shutil.which("dirname"), self.bin / "dirname")
        self.fake_python("python3")

    def fake_python(self, name, probe_ok=True, folder=None, probe_status=None):
        path = (folder or self.bin) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if probe_status is None:
            probe_status = 0 if probe_ok else 1
        path.write_text(
            '#!/bin/sh\ncase "$2" in "import sys; ok ="*) exit %d ;; esac\nexec %s "$@"\n'
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

    def test_existing_environment_is_still_checked_when_only_old_python_is_available(self):
        python = self.fake_python("python3", probe_status=3)
        python.write_text(python.read_text().replace('case "$2" in', 'case "$2" in "import PyQt6.QtWidgets") exit 0 ;;'))
        result = self.run_start()
        self.assertEqual(result.returncode, 0)
        self.assertIn("APP_STARTED", result.stdout)

    def test_log_failure_does_not_prevent_launch(self):
        (self.home / ".rokey-study" / "launch.log").mkdir(parents=True)
        result = self.run_start()
        self.assertEqual(result.returncode, 0)
        self.assertIn("APP_STARTED", result.stdout)

    def test_log_privacy_does_not_change_the_app_umask(self):
        (self.repo / "study.py").write_text("import os\nprint('UMASK=' + str(os.umask(0)))\n")
        result = subprocess.run(['/bin/sh', '-c', 'umask 022; exec "$1"', 'sh', str(self.script)],
                                cwd=self.base, env=self.env, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("UMASK=18", result.stdout)

    def test_missing_and_unusable_python_offer_installation_without_network_on_eof(self):
        for exists in (True, False):
            with self.subTest(exists=exists):
                self.fake_python("python3", probe_ok=False)
                if not exists:
                    (self.bin / "python3").unlink()
                result = self.run_start()
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("설치를 취소했습니다", result.stdout)
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
        os.write(master, b"y\n\n")
        until("Enter를 누르면 종료")
        with self.assertRaises(subprocess.TimeoutExpired):
            proc.wait(timeout=0.5)
        self.assertIn(b"ANSWER=y", output)
        os.write(master, b"\n")
        self.assertEqual(proc.wait(timeout=5), 23)

    def test_probe_agrees_with_bootstrap_version_and_bits(self):
        script = (ROOT / "start.command").read_text()
        probe = script.split("try_python()", 1)[1].split("-c '", 1)[1].split("'", 1)[0]
        # 실제 실행기의 검사식을 여러 버전과 비트 수로 실행함.
        for version in ((3, 9), (3, 10), (3, 14), (3, 15)):
            for bits in (32, 64):
                source = "import sys\nsys.version_info=%r\nsys.maxsize=%d\n%s" % (version, 2 ** (bits - 1) - 1, probe)
                result = subprocess.run([sys.executable, "-c", source], capture_output=True, timeout=5)
                expected = bootstrap.python_problem({"version": version, "bits64": bits == 64, "platform": "macosx"})
                self.assertEqual(result.returncode == 0, expected is None, (version, bits))

    def test_decline_then_reopen_asks_again_without_an_error(self):
        import pty
        self.env["PYTHONDONTWRITEBYTECODE"] = "1"
        shutil.copyfile(ROOT / "study.py", self.repo / "study.py")
        # 실제 진입·동의 경로를 쓰고 설치·화면 실행만 대역으로 바꿈.
        (self.repo / "bootstrap.py").write_text((ROOT / "bootstrap.py").read_text() + '''
Host.python_info = lambda self: {"version": (3, 14), "bits64": True, "platform": "macosx", "prefix": "/test-python"}
Host.pyqt_error = lambda self: "ModuleNotFoundError: No module named PyQt6"
Host.can_venv = lambda self: True
Host.probe = lambda self, python: False
Host.remove = lambda self, path: self.say("FAKE_REMOVE")
Host.create_venv = lambda self, path: self.say("FAKE_CREATE")
Host.pip_install = lambda self, python: (0, "")
Host.call = lambda self, command: self.say("FAKE_APP_STARTED") or 0
''')

        def run_once(answer):
            master, slave = pty.openpty()
            proc = subprocess.Popen([str(self.script)], cwd=self.base, env=self.env,
                                    stdin=slave, stdout=slave, stderr=slave)
            os.close(slave)
            output = b""
            answered = dismissed = False
            deadline = time.monotonic() + 10
            try:
                while time.monotonic() < deadline:
                    ready, _, _ = select.select([master], [], [], 0.1)
                    if ready:
                        try:
                            chunk = os.read(master, 8192)
                        except OSError as error:
                            if error.errno == errno.EIO:  # Linux PTY는 자식 종료 뒤 EIO를 돌려줌.
                                break
                            raise
                        if not chunk:
                            break
                        output += chunk
                    if not answered and "설치할까요? [y/N] ".encode() in output:
                        os.write(master, answer.encode() + b"\n")
                        answered = True
                    if not dismissed and "Enter를 누르면 종료".encode() in output:
                        os.write(master, b"\n")
                        dismissed = True
                    if proc.poll() is not None and not ready:
                        break
                self.assertTrue(answered, output.decode(errors="replace"))
                return proc.wait(timeout=2), output.decode(errors="replace")
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait()
                os.close(master)

        def files():
            return {p.relative_to(self.home): p.read_bytes() if p.is_file() else None
                    for p in self.home.rglob("*") if p != self.home / ".rokey-study"}

        for state in ("none", "empty", "broken"):
            with self.subTest(state=state):
                venv = self.home / ".rokey-study" / ("venv-" + state)
                self.env["STUDY_VENV"] = str(venv)
                if state != "none":
                    venv.mkdir(parents=True)
                if state == "broken":
                    (venv / "pyvenv.cfg").write_text("existing environment\n")
                before = files()
                code, text = run_once("n")
                self.assertEqual(code, 0, text)
                self.assertIn("설치를 취소했습니다", text)
                self.assertNotIn("프로그램을 열지 못했습니다", text)
                self.assertNotIn("Enter를 누르면 종료", text)
                self.assertNotIn("FAKE_", text)
                after = files()
                before.pop(Path(".rokey-study/launch.log"), None)
                after.pop(Path(".rokey-study/launch.log"))
                self.assertEqual(before, after)
                code, text = run_once("y")
                self.assertEqual(code, 0, text)
                self.assertIn("FAKE_CREATE", text)
                self.assertIn("FAKE_APP_STARTED", text)
                self.assertEqual("FAKE_REMOVE" in text, state == "broken")
                self.assertNotIn("Enter를 누르면 종료", text)


if __name__ == "__main__":
    unittest.main()

    def test_certificate_retry_does_not_block_a_working_python(self):
        pending = self.home / ".rokey-study/python-certificates.pending"
        pending.parent.mkdir()
        pending.touch()
        for code in (1, 2):
            (self.repo / "tools/install_python_macos.sh").write_text("exit %d\n" % code)
            result = self.run_start()
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("APP_STARTED", result.stdout)
            self.assertTrue(pending.exists())

    def test_install_success_continues_to_the_program(self):
        (self.bin / "python3").unlink()
        path = self.base / "Library/Frameworks/Python.framework/Versions/3.14/bin/python3.14"
        helper = self.repo / "tools/install_python_macos.sh"
        helper.write_text("#!/bin/sh\n/bin/mkdir -p " + shlex.quote(str(path.parent)) +
                          "\n/bin/ln -s " + shlex.quote(sys.executable) + " " + shlex.quote(str(path)) + "\n")
        result = self.run_start()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("APP_STARTED", result.stdout)

    def test_existing_healthy_environment_does_not_download_python(self):
        (self.bin / "python3").unlink()
        python = self.fake_python("python", folder=self.home / ".rokey-study/venv/bin")
        python.write_text(python.read_text().replace('case "$2" in', 'case "$2" in "import PyQt6.QtWidgets") exit 0 ;;'))
        result = self.run_start()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("APP_STARTED", result.stdout)
        self.assertNotIn("내려받", result.stdout)

    @unittest.skipUnless(sys.platform == "darwin", "macOS 앱 실행 경로")
    def test_app_opens_start_command_when_python_is_missing(self):
        script = (ROOT / "ROKEY.app/Contents/MacOS/ROKEY").read_text()
        script = script.replace('extra="/opt/homebrew/bin:/usr/local/bin:/Library/Frameworks/Python.framework/Versions/Current/bin"', 'extra=""')
        launcher = self.repo / "ROKEY.app/Contents/MacOS/ROKEY"
        launcher.parent.mkdir(parents=True)
        opened = self.base / "opened"
        opener = self.bin / "open"
        opener.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > ' + shlex.quote(str(opened)) + '\n')
        opener.chmod(0o755)
        script = script.replace('/usr/bin/open', shlex.quote(str(opener)))
        launcher.write_text(script)
        (self.repo / "start.pyw").touch()
        self.fake_python("python3", probe_ok=False, probe_status=1).write_text('#!/bin/sh\nexit 1\n')
        result = subprocess.run(["/bin/zsh", "-f", str(launcher)], cwd=self.base, env=self.env,
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(opened.read_text().strip(), str(self.script))


@unittest.skipUnless(os.name == "posix", "POSIX 설치 경로 검사")
class MacPythonInstallTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="mac-python-install-")
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name) / "한글 설치 폴더"
        self.base.mkdir()
        self.home = self.base / "home"
        self.home.mkdir()
        self.trace = self.base / "calls"
        self.env = dict(os.environ, HOME=str(self.home), TRACE=str(self.trace))
        self.script = self.base / "install.sh"
        source = (ROOT / "tools/install_python_macos.sh").read_text()
        self.commands = {}
        for name in ("curl", "shasum", "pkgutil", "osascript", "lockf"):
            path = self.base / name
            self.commands[name] = path
            original = ("/usr/sbin/" if name == "pkgutil" else "/usr/bin/") + name
            self.assertIn(original, source)
            source = source.replace(original, shlex.quote(str(path)))
        self.runtime = self.base / "python"
        source = source.replace("runtime=/Library/Frameworks/Python.framework/Versions/3.14/bin/python3.14",
                                "runtime=" + shlex.quote(str(self.runtime)))
        self.certificates = self.base / "Install Certificates.command"
        source = source.replace("'/Applications/Python 3.14/Install Certificates.command'", shlex.quote(str(self.certificates)))
        self.script.write_text(source)
        self.stub("curl", 'printf "download\\n" >> "$TRACE"; exit "${DOWNLOAD_STATUS:-0}"')
        self.stub("shasum", 'printf "%s  python.pkg\\n" "${HASH:-286c7018aa2730f6747ca433dccdc2b31be45f078a9ea0ffa44d5f06368fd2d7}"')
        self.stub("pkgutil", 'printf "%s\\n" "${SIGNER:-Developer ID Installer: Python Software Foundation (BMM5U3QVKW)}"; exit "${SIGNATURE_STATUS:-0}"')
        self.stub("lockf", '[ "${LOCK_STATUS:-0}" = 0 ] || exit "$LOCK_STATUS"; shift 4; exec "$@"')
        self.stub("osascript", 'printf "install\\n" >> "$TRACE"; /bin/cat >/dev/null; printf "%s" "${INSTALL_RESULT:-installed}"; exit "${INSTALL_STATUS:-0}"')
        self.runtime.write_text('#!/bin/sh\ncase "$2" in "import ssl, venv") exit 1 ;; esac\nprintf "python\\n" >> "$TRACE"\n')
        self.runtime.chmod(0o755)
        self.certificates.write_text('printf "certificates\\n" >> "$TRACE"; exit "${CERT_STATUS:-0}"\n')

    def stub(self, name, text):
        self.commands[name].write_text("#!/bin/sh\n" + text + "\n")
        self.commands[name].chmod(0o755)

    def run_install(self, answer="y\n", **values):
        return subprocess.run(["/bin/sh", str(self.script)], env=dict(self.env, **values), input=answer,
                              capture_output=True, text=True, timeout=10)

    def calls(self):
        return self.trace.read_text().splitlines() if self.trace.exists() else []

    def assert_clean(self):
        folder = self.home / ".rokey-study"
        self.assertEqual([p.name for p in folder.iterdir() if p.name != "python-certificates.pending"] if folder.exists() else [], [])

    def test_decline_then_retry_only_downloads_after_yes(self):
        for answer in ("n\n", "", "\n"):
            self.assertEqual(self.run_install(answer).returncode, 2)
            self.assertEqual(self.calls(), [])
            self.assert_clean()
        result = self.run_install()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls(), ["download", "install", "python"])
        self.assert_clean()

    def test_bad_hash_or_signature_never_runs_installer(self):
        for env in ({"HASH": "wrong"}, {"SIGNER": "someone else"}, {"SIGNATURE_STATUS": "1"}):
            with self.subTest(env=env):
                self.trace.unlink(missing_ok=True)
                result = self.run_install(**env)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(self.calls(), ["download"])
                self.assert_clean()

    def test_download_or_os_permission_failure_is_retryable(self):
        for env, expected in (({"DOWNLOAD_STATUS": "22"}, ["download"]),
                              ({"INSTALL_STATUS": "1"}, ["download", "install"])):
            with self.subTest(env=env):
                self.trace.unlink(missing_ok=True)
                self.assertNotEqual(self.run_install(**env).returncode, 0)
                self.assertEqual(self.calls(), expected)
                self.assert_clean()
                self.assertEqual(self.run_install().returncode, 0)
                self.assert_clean()

    def test_another_install_never_downloads_or_removes_its_lock(self):
        folder = self.home / ".rokey-study"
        folder.mkdir()
        lock = folder / "python-install.lock"
        lock.write_text("another process")
        self.assertNotEqual(self.run_install(LOCK_STATUS="1").returncode, 0)
        self.assertEqual(self.calls(), [])
        self.assertEqual(lock.read_text(), "another process")

    @unittest.skipUnless(sys.platform == "darwin", "macOS lockf 검사")
    def test_system_lock_reuses_a_file_after_owner_exit(self):
        lock = self.base / "lock"
        lock.write_text("previous process\n")
        for _ in range(2):
            subprocess.run(["/usr/bin/lockf", "-sk", "-t", "0", str(lock), "/usr/bin/true"], check=True)

    def test_cancel_admin_dialog_keeps_previous_certificate_retry(self):
        self.assertEqual(self.run_install(INSTALL_RESULT="cancelled").returncode, 2)
        pending = self.home / ".rokey-study/python-certificates.pending"
        self.assertFalse(pending.exists())
        self.assertNotEqual(self.run_install(INSTALL_STATUS="1").returncode, 0)
        self.assertTrue(pending.exists())
        self.assertEqual(self.run_install(INSTALL_RESULT="cancelled").returncode, 2)
        self.assertTrue(pending.exists())
        self.assertEqual(self.run_install().returncode, 0)
        self.assertFalse(pending.exists())

    def test_certificate_only_retry_skips_the_pkg_download(self):
        folder = self.home / ".rokey-study"
        folder.mkdir()
        pending = folder / "python-certificates.pending"
        pending.touch()
        self.runtime.write_text('#!/bin/sh\nexit 0\n')
        self.assertEqual(self.run_install().returncode, 0)
        self.assertEqual(self.calls(), ["install"])
        self.assertFalse(pending.exists())
