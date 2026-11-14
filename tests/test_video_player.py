"""문서·주소와 고정한 Qt 구성의 설치 계획을 외부 연결 없이 검사함."""
from pathlib import Path
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest import mock

from career import player_html as player
from tools import video_setup

CORE = {"PyQt6": "6.11.0", "PyQt6-Qt6": "6.11.2", "PyQt6-sip": "13.13.0"}
VIDEO = "H89Az-iZZrc"


def report(*packages):
    return {"install": [{"metadata": {"name": name, "version": version}} for name, version in packages]}


class PlayerDocumentTest(unittest.TestCase):
    def test_document_contains_only_validated_public_identity_and_official_player(self):
        source = player.player_html(VIDEO)
        self.assertIn("https://www.youtube-nocookie.com/embed/" + VIDEO, source)
        self.assertIn("origin=https%3A%2F%2Frokey.python.study", source)
        for value in ("autoplay=0", "controls=1", "fs=1", "cc_lang_pref=ko", "allowfullscreen",
                      "player.playVideo()", "onAutoplayBlocked", "onStateChange", "onError", "pagehide", "player.destroy()",
                      "min-width:200px", "min-height:200px"):
            self.assertIn(value, source)
        for value in ("modestbranding", "rel=0", "font-size", "localStorage", "fetch(", "token"):
            self.assertNotIn(value, source)
        root = Path(__file__).resolve().parents[1]
        self.assertIn('APP_ID = "' + player.APP_ID + '"', (root / "gui/icon.py").read_text())

    def test_injection_and_malformed_ids_are_rejected(self):
        for value in (None, 33, "", VIDEO + "\n", "a" * 12, "<script>bad", "http://host", "あ" * 11):
            with self.subTest(value=value), self.assertRaises(ValueError):
                player.player_html(value)

    def test_only_selected_embed_is_internal(self):
        self.assertTrue(player.is_embed_url(player.embed_url(VIDEO), VIDEO))
        for url in ("https://www.youtube.com/embed/" + VIDEO,
                    "https://www.youtube-nocookie.com/embed/abcdefghijk",
                    "https://www.youtube-nocookie.com.evil.test/embed/" + VIDEO,
                    "https://name@www.youtube-nocookie.com/embed/" + VIDEO,
                    "http://www.youtube-nocookie.com/embed/" + VIDEO,
                    "https://www.youtube-nocookie.com:444/embed/" + VIDEO):
            self.assertFalse(player.is_embed_url(url, VIDEO), url)

    def test_external_urls_reject_login_redirects_and_untrusted_hosts(self):
        for url in (player.watch_url(VIDEO), "https://youtu.be/" + VIDEO,
                    "https://www.youtube.com/@robot", "https://www.youtube.com/channel/UCabc"):
            self.assertTrue(player.external_video_link(url), url)
        for url in ("https://accounts.google.com/", "javascript:alert(1)", "file:///tmp/a",
                    "https://www.youtube.com/redirect?q=https://example.com",
                    "https://www.youtube.com/signin", "https://youtube.com:broken/watch?v=" + VIDEO,
                    "https://www.youtube.com.evil.test/watch?v=" + VIDEO,
                    "https://secret@www.youtube.com/watch?v=" + VIDEO):
            self.assertFalse(player.external_video_link(url), url)

    def test_playback_subframes_do_not_filter_ads_but_reject_login_or_another_video(self):
        for url in (player.embed_url(VIDEO), "https://googleads.g.doubleclick.net/pagead/html/example",
                    "https://tpc.googlesyndication.com/safeframe/example"):
            self.assertTrue(player.is_playback_frame(url, VIDEO), url)
        for url in ("https://accounts.google.com/", "https://www.youtube.com/watch?v=" + VIDEO,
                    player.embed_url("abcdefghijk"), "file:///tmp/a"):
            self.assertFalse(player.is_playback_frame(url, VIDEO), url)

    def test_deleted_embed_denial_and_missing_identity_are_distinct(self):
        self.assertIn("삭제", player.error_message(100))
        self.assertEqual(player.error_message(101), player.error_message(150))
        self.assertIn("식별", player.error_message(153))
        self.assertIn("연결", player.error_message(999))

    @unittest.skipUnless(shutil.which("node"), "Node.js가 없어 HTML 이벤트 검사를 건너뜁니다.")
    def test_html_error_is_terminal_while_normal_events_keep_their_order(self):
        script = re.search(r"<script>([\s\S]*?)</script>", player.player_html(VIDEO)).group(1)
        harness = '''const vm = require('node:vm'), fs = require('node:fs');
const assert = require('node:assert/strict');
let events, plays = 0;
const context = {window: {addEventListener: () => {}},
document: {createElement: () => ({}), head: {appendChild: () => {}}},
YT: {Player: function(id, options) {events = options.events; return {playVideo() {plays++;}, stopVideo() {}, destroy() {}};}}};
vm.createContext(context); vm.runInContext(fs.readFileSync(0, 'utf8'), context);
context.onYouTubeIframeAPIReady();
const attempt = context.window.tryRokeyPlayback;
attempt(true); assert.equal(plays, 0);
events.onReady(); assert.equal(context.window.rokeyState.kind, 'ready');
attempt(false); context.document.hidden = true; attempt(true); assert.equal(plays, 0);
context.document.hidden = false; attempt(true); assert.equal(plays, 1);
events.onAutoplayBlocked(); attempt(true); assert.equal(plays, 1);
assert.equal(context.window.rokeyState.kind, 'blocked');
assert.equal(context.window.rokeyState.initial, false);
for (const value of [1, 2, 3, -1, 5]) {
events.onStateChange({data: value}); assert.equal(context.window.rokeyState.code, value); }
events.onError({data: 150});
events.onStateChange({data: -1}); events.onReady(); events.onAutoplayBlocked();
events.onStateChange({data: 1}); events.onError({data: 153});
assert.equal(context.window.rokeyState.kind, 'error'); assert.equal(context.window.rokeyState.code, 150);
console.log('terminal error retained');'''
        result = subprocess.run([shutil.which("node"), "-e", harness], input=script,
                                text=True, capture_output=True, timeout=10)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("terminal error retained", result.stdout)


class InstallerTest(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.TemporaryDirectory()
        self.addCleanup(self.home.cleanup)
        self.temp = mock.patch("tools.video_setup.tempfile.gettempdir", return_value=self.home.name)
        self.temp.start()
        self.addCleanup(self.temp.stop)
        self.import_probe = mock.Mock(return_value=True)
        safety = mock.patch("tools.video_setup._import_probe", self.import_probe)
        safety.start()
        self.addCleanup(safety.stop)
        self.cancel = threading.Event()
        self.core = dict(CORE)
        self.calls = []
        self.plan = report(("PyQt6-WebEngine", "6.11.0"), ("PyQt6-WebEngine-Qt6", "6.11.2"))

    def runner(self, args, cancel, applying=False):
        self.calls.append((args, applying))
        constraints = Path(args[args.index("--constraint") + 1]).read_text()
        self.assertEqual(set(constraints.splitlines()), {f"{k}=={v}" for k, v in self.core.items()})
        if "--report" in args:
            Path(args[args.index("--report") + 1]).write_text(json.dumps(self.plan))
        return subprocess.CompletedProcess(args, 0)

    def install(self, **kwargs):
        return video_setup.install(self.cancel, runner=self.runner, versions=lambda: dict(self.core),
                                   import_probe=self.import_probe, **kwargs)

    def test_success_pins_core_and_installs_only_exact_engine_wheels(self):
        result = self.install()
        self.assertTrue(result["ok"])
        self.assertTrue(result["restart"])
        self.assertEqual(2, len(self.calls))
        probe, install = self.calls
        self.assertIn("--dry-run", probe[0])
        self.assertIn("--no-deps", install[0])
        self.assertTrue(install[1])
        for args, _ in self.calls:
            self.assertEqual(args[:4], [sys.executable, "-m", "pip", "--isolated"])
            self.assertIn("--only-binary=:all:", args)
            self.assertNotIn("--upgrade", args)
        self.assertIn("PyQt6-WebEngine-Qt6==6.11.2", probe[0])
        self.assertEqual(install[0][-2:], ["pyqt6-webengine==6.11.0", "pyqt6-webengine-qt6==6.11.2"])
        self.import_probe.assert_called_once_with()
        self.assertEqual(b"\0", video_setup._lock_path().read_bytes())

    def test_different_minor_core_mutation_and_unrelated_dependency_are_refused(self):
        for name, version in (("PyQt6-WebEngine", "6.12.0"), ("PyQt6", "6.11.0"),
                              ("PyQt6-Qt6", "6.11.2"), ("PyQt6-sip", "13.13.0"), ("numpy", "2.4.0")):
            self.calls.clear()
            self.plan = report((name, version))
            with self.subTest(name=name):
                result = self.install()
                self.assertFalse(result["ok"])
                self.assertFalse(result["restart"])
                self.assertEqual(1, len(self.calls))

    def test_mismatched_installed_qt_is_refused_before_pip(self):
        core = dict(CORE, PyQt6="6.10.0")
        result = video_setup.install(runner=self.runner, versions=lambda: core)
        self.assertFalse(result["ok"])
        self.assertEqual([], self.calls)

    def test_cancel_before_plan_and_after_plan_never_installs(self):
        self.cancel.set()
        self.assertEqual("cancelled", self.install()["status"])
        self.assertEqual([], self.calls)
        self.cancel.clear()
        def cancel_after_plan(args, cancel, applying=False):
            result = self.runner(args, cancel, applying)
            cancel.set()
            return result
        result = video_setup.install(self.cancel, runner=cancel_after_plan, versions=lambda: CORE)
        self.assertEqual("cancelled", result["status"])
        self.assertEqual(1, len(self.calls))

    def test_cancel_during_install_reports_cancelled_after_finishing(self):
        def cancel_during_install(args, cancel, applying=False):
            if applying:
                cancel.set()
            return self.runner(args, cancel, applying)
        result = video_setup.install(self.cancel, runner=cancel_during_install, versions=lambda: CORE)
        self.assertEqual("cancelled", result["status"])
        self.assertTrue(result["installed"])
        self.assertFalse(result["restart"])

    def test_pip_failure_and_locked_core_leave_retry_available(self):
        for error in (PermissionError("locked"), subprocess.CompletedProcess([], 1)):
            runner = mock.Mock(side_effect=error) if isinstance(error, Exception) else mock.Mock(return_value=error)
            result = video_setup.install(runner=runner, versions=lambda: CORE)
            self.assertEqual("error", result["status"])
            self.assertFalse(result["restart"])
            self.assertTrue(self.install()["ok"])

    def test_core_change_during_probe_prevents_application(self):
        versions = mock.Mock(side_effect=[CORE, dict(CORE, PyQt6="6.12.0")])
        result = video_setup.install(runner=self.runner, versions=versions)
        self.assertFalse(result["ok"])
        self.assertEqual(1, len(self.calls))

    def test_locked_engine_files_during_application_do_not_request_restart(self):
        def locked(args, cancel, applying=False):
            result = self.runner(args, cancel, applying)
            if applying:
                raise PermissionError("locked")
            return result
        result = video_setup.install(runner=locked, versions=lambda: dict(CORE))
        self.assertEqual("error", result["status"])
        self.assertFalse(result["restart"])
        self.assertEqual(2, len(self.calls))
        self.assertTrue(self.install()["ok"])

    def test_duplicate_and_malformed_reports_are_refused(self):
        for value in ({}, {"install": None}, report(("PyQt6-WebEngine", "6.11.0"), ("pyqt6_webengine", "6.11.0"))):
            self.plan = value
            self.calls.clear()
            self.assertFalse(self.install()["ok"])
            self.assertEqual(1, len(self.calls))

    def test_another_preparation_lock_is_not_removed(self):
        key = video_setup.hashlib.sha256(video_setup.os.path.realpath(sys.prefix).encode()).hexdigest()[:20]
        lock = Path(self.home.name) / ("rokey-video-" + key + ".lock")
        descriptor = video_setup._acquire_lock(lock)
        try:
            result = self.install()
            self.assertFalse(result["ok"])
            self.assertEqual([], self.calls)
        finally:
            os.close(descriptor)
        self.assertEqual(b"\0", lock.read_bytes())
        inode = lock.stat().st_ino
        self.assertTrue(self.install()["ok"])
        self.assertEqual(inode, lock.stat().st_ino)

    def test_runtime_patch_is_exact_and_binding_patch_may_differ(self):
        for version in ("6.11.1", "6.11.3"):
            self.calls.clear()
            self.plan = report(("PyQt6-WebEngine-Qt6", version))
            self.assertFalse(self.install()["ok"])
            self.assertEqual(1, len(self.calls))
        self.import_probe.assert_not_called()
        self.plan = report(("PyQt6-WebEngine", "6.11.1"), ("PyQt6-WebEngine-Qt6", "6.11.2"))
        self.assertTrue(self.install()["ok"])

    def test_failed_import_never_reports_success_even_for_an_empty_plan(self):
        self.import_probe.return_value = False
        before = dict(CORE)
        result = self.install()
        self.assertFalse(result["ok"])
        self.assertFalse(result["restart"])
        self.assertIn("불러오지 못했습니다", result["message"])
        self.assertEqual(2, len(self.calls))
        self.plan = report()
        self.calls.clear()
        result = self.install()
        self.assertFalse(result["ok"])
        self.assertFalse(result["restart"])
        self.assertEqual(1, len(self.calls))
        self.assertEqual(before, CORE)
        self.assertEqual(2, self.import_probe.call_count)

    def test_import_timeout_and_cancellation_do_not_request_restart(self):
        self.import_probe.side_effect = subprocess.TimeoutExpired("mock import", 30)
        self.assertFalse(self.install()["restart"])
        self.import_probe.side_effect = lambda: (self.cancel.set(), True)[1]
        self.assertEqual("cancelled", self.install()["status"])

    def test_confirmed_split_pair_uses_exact_requests_constraints_and_import_probe(self):
        self.core.update({"PyQt6": "6.12.0", "PyQt6-Qt6": "6.12.0"})
        before = dict(self.core)
        self.plan = report(("PyQt6-WebEngine", "6.140.0"), ("PyQt6-WebEngine-Qt6", "6.140.0"))
        result = self.install()
        self.assertTrue(result["ok"])
        self.assertTrue(result["restart"])
        probe, apply = self.calls
        self.assertEqual(["PyQt6-WebEngine==6.140.0", "PyQt6-WebEngine-Qt6==6.140.0"], probe[0][-2:])
        self.assertEqual(["pyqt6-webengine==6.140.0", "pyqt6-webengine-qt6==6.140.0"], apply[0][-2:])
        self.assertIn("--no-deps", apply[0])
        self.assertTrue(apply[1])
        self.import_probe.assert_called_once_with()
        self.assertEqual(before, self.core)
        self.plan = report()
        self.import_probe.return_value = False
        self.assertFalse(self.install()["restart"])

    def test_split_pair_rejects_older_core_unconfirmed_engine_patches_and_mixed_versions(self):
        mapped = dict(CORE, **{"PyQt6": "6.12.0", "PyQt6-Qt6": "6.12.0"})
        for core, binding, runtime in ((CORE, "6.140.0", "6.140.0"),
                                       (mapped, "6.140.1", "6.140.0"),
                                       (mapped, "6.140.0", "6.140.1"),
                                       (mapped, "6.140.0", "6.12.0"),
                                       (mapped, "6.12.0", "6.140.0"),
                                       (mapped, "6.11.0", "6.140.0")):
            with self.subTest(core=core, binding=binding, runtime=runtime), self.assertRaises(ValueError):
                video_setup.checked_plan(report(("PyQt6-WebEngine", binding), ("PyQt6-WebEngine-Qt6", runtime)), core)

    def test_unconfirmed_new_core_patches_and_releases_fall_back_before_pip(self):
        for version in ("6.12.1", "6.13.0"):
            self.core.update({"PyQt6": version, "PyQt6-Qt6": version})
            self.assertFalse(self.install()["ok"])
        self.assertEqual([], self.calls)
        self.import_probe.assert_not_called()

    def test_mapped_core_allows_only_the_6_12_binding_minor(self):
        plan = report(("PyQt6-WebEngine", "6.140.0"), ("PyQt6-WebEngine-Qt6", "6.140.0"))
        core = dict(CORE, **{"PyQt6": "6.12.1", "PyQt6-Qt6": "6.12.0"})
        self.assertEqual(["pyqt6-webengine==6.140.0", "pyqt6-webengine-qt6==6.140.0"],
                         video_setup.checked_plan(plan, core))
        for binding in ("6.11.9", "6.13.0"):
            core["PyQt6"] = binding
            with self.assertRaises(ValueError):
                video_setup.checked_plan(plan, core)


class ProcessAndLockTest(unittest.TestCase):
    def test_applying_waits_past_old_deadline_even_after_cancel(self):
        process = mock.Mock(returncode=0)
        process.poll.return_value = 0
        process.wait.side_effect = [subprocess.TimeoutExpired("mock pip", .1)] * 3601 + [0]
        cancel = threading.Event()
        cancel.set()
        with mock.patch("tools.video_setup.subprocess.Popen", return_value=process), \
                mock.patch("tools.video_setup.time.monotonic", side_effect=[0, 99999]):
            result = video_setup._run(["mock pip"], cancel, applying=True)
        self.assertEqual(0, result.returncode)
        process.terminate.assert_not_called()
        process.kill.assert_not_called()
        self.assertEqual(3602, process.wait.call_count)

    def test_plan_timeout_and_cancel_can_terminate(self):
        for cancelled in (True, False):
            process = mock.Mock(returncode=-15)
            process.poll.return_value = -15
            process.wait.side_effect = [subprocess.TimeoutExpired("mock pip", .1), -15]
            cancel = threading.Event()
            if cancelled:
                cancel.set()
            with mock.patch("tools.video_setup.subprocess.Popen", return_value=process), \
                    mock.patch("tools.video_setup.time.monotonic", side_effect=[0, 361]):
                self.assertEqual(-15, video_setup._run(["mock pip"], cancel).returncode)
            process.terminate.assert_called_once()
            process.wait.assert_called_with(timeout=5)
            process.kill.assert_not_called()

    def test_import_probe_is_a_separate_import_without_an_application(self):
        for code in (0, 1, -6):
            with mock.patch("tools.video_setup.subprocess.run", return_value=subprocess.CompletedProcess([], code)) as run:
                self.assertEqual(code == 0, video_setup._import_probe())
            command = run.call_args.args[0]
            self.assertEqual([sys.executable, "-I", "-c"], command[:3])
            self.assertEqual("from PyQt6.QtWebEngineWidgets import QWebEngineView", command[-1])
            self.assertEqual(30, run.call_args.kwargs["timeout"])

    def test_windows_lock_contract_uses_one_byte_from_the_start(self):
        windows = SimpleNamespace(LK_NBLCK=2, locking=mock.Mock())
        with tempfile.TemporaryDirectory() as folder, mock.patch.dict(sys.modules, {"msvcrt": windows}), \
                mock.patch("tools.video_setup.sys.platform", "win32"):
            path = Path(folder) / "lock"
            descriptor = video_setup._acquire_lock(path)
            try:
                windows.locking.assert_called_once_with(descriptor, 2, 1)
                self.assertEqual(0, os.lseek(descriptor, 0, os.SEEK_CUR))
            finally:
                os.close(descriptor)
            self.assertEqual(b"\0", path.read_bytes())

    def test_competing_process_is_refused_and_killed_owner_releases_lock(self):
        holder_code = ("import os,sys; from tools.video_setup import _acquire_lock; "
                       "fd=_acquire_lock(sys.argv[1]); print('locked',flush=True); "
                       "sys.stdin.readline(); os.close(fd)")
        contender_code = ("import os,sys\nfrom tools.video_setup import _acquire_lock\n"
                          "try: fd=_acquire_lock(sys.argv[1])\n"
                          "except OSError: sys.exit(7)\n"
                          "else: os.close(fd)\n")
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "lock"
            holder = subprocess.Popen([sys.executable, "-u", "-c", holder_code, str(path)],
                                      stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                ready = queue.Queue()
                threading.Thread(target=lambda: ready.put(holder.stdout.readline()), daemon=True).start()
                self.assertEqual("locked\n", ready.get(timeout=5))
                inode = path.stat().st_ino
                second = subprocess.run([sys.executable, "-c", contender_code, str(path)], capture_output=True, timeout=5)
                self.assertEqual(7, second.returncode, second.stderr)
                holder.kill()
                holder.wait(timeout=5)
                third = subprocess.run([sys.executable, "-c", contender_code, str(path)], capture_output=True, timeout=5)
                self.assertEqual(0, third.returncode, third.stderr)
                self.assertEqual(inode, path.stat().st_ino)
                self.assertEqual(b"\0", path.read_bytes())
            finally:
                if holder.poll() is None:
                    holder.kill()
                    holder.wait(timeout=5)
                for stream in (holder.stdin, holder.stdout, holder.stderr):
                    stream.close()


if __name__ == "__main__":
    unittest.main()
