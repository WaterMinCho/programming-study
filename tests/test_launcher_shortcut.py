# -*- coding: utf-8 -*-
"""바로가기의 경로 전달·기존 파일 보존·실패 복구를 확인함."""
import base64
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from gui import launcher_shortcut as shortcut


class ShortcutTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="study 한글 ' & $ [ , ")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.start = self.root / "start.pyw"
        self.start.write_text("", encoding="utf-8")
        self.python = self.root / "python" / "python.exe"
        self.python.parent.mkdir()
        self.pythonw = self.python.with_name("pythonw.exe")
        self.pythonw.write_bytes(b"")

    def create(self):
        with mock.patch.object(shortcut.sys, "platform", "win32"):
            return shortcut.create(self.root, self.python)

    def save(self, script, payload):
        Path(payload["link"]).write_bytes(b"shortcut")
        self.assertEqual(payload["target"], str(self.pythonw))
        self.assertEqual(payload["arguments"], subprocess.list2cmdline([str(self.start)]))
        self.assertEqual(payload["workdir"], str(self.root))
        self.assertEqual(payload["icon"], str(self.root / shortcut.CACHE / "icon.ico") + ",0")

    def test_project_link_uses_the_running_pythonw_and_absolute_paths(self):
        with mock.patch.object(shortcut, "powershell", side_effect=self.save) as shell, \
                mock.patch.object(shortcut, "icon_bytes", return_value=b"icon"):
            link = self.create()
        self.assertEqual(link, self.root / shortcut.NAME)
        self.assertEqual(link.read_bytes(), b"shortcut")
        self.assertEqual((self.root / shortcut.CACHE / "icon.ico").read_bytes(), b"icon")
        self.assertEqual(list((self.root / shortcut.CACHE).iterdir()), [self.root / shortcut.CACHE / "icon.ico"])
        self.assertEqual(sorted(path.name for path in self.root.iterdir()),
                         sorted([shortcut.NAME, shortcut.CACHE, "python", "start.pyw"]))
        self.assertIsNone(self.create())
        self.assertEqual(shell.call_count, 1)

    def test_existing_files_and_directories_are_never_overwritten(self):
        for directory in (False, True):
            with self.subTest(directory=directory):
                link = self.root / shortcut.NAME
                if directory:
                    link.mkdir()
                else:
                    link.write_bytes(b"someone else's shortcut")
                with mock.patch.object(shortcut, "powershell") as shell:
                    self.assertIsNone(self.create())
                shell.assert_not_called()
                self.assertFalse((self.root / shortcut.CACHE).exists())
                if directory:
                    link.rmdir()
                else:
                    self.assertEqual(link.read_bytes(), b"someone else's shortcut")
                    link.unlink()

    def test_a_file_created_while_saving_is_preserved(self):
        link = self.root / shortcut.NAME

        def collision(source, target):
            link.write_bytes(b"someone else's shortcut")
            raise FileExistsError()

        with mock.patch.object(shortcut, "powershell", side_effect=self.save), \
                mock.patch.object(shortcut, "icon_bytes", return_value=b"icon"), \
                mock.patch.object(shortcut.os, "rename", side_effect=collision):
            self.assertIsNone(self.create())
        self.assertEqual(link.read_bytes(), b"someone else's shortcut")

    def test_missing_pythonw_or_entry_does_not_fall_back_to_console_python(self):
        for missing in (self.pythonw, self.start):
            with self.subTest(missing=missing):
                missing.unlink()
                with mock.patch.object(shortcut, "powershell") as shell:
                    with self.assertRaises(FileNotFoundError):
                        self.create()
                shell.assert_not_called()
                self.assertFalse((self.root / shortcut.CACHE).exists())
                missing.write_bytes(b"")

    def test_shell_failure_leaves_no_partial_link_and_can_be_retried(self):
        with mock.patch.object(shortcut, "icon_bytes", return_value=b"icon"), \
                mock.patch.object(shortcut, "powershell", side_effect=subprocess.TimeoutExpired("powershell", 15)):
            with self.assertRaises(subprocess.TimeoutExpired):
                self.create()
        self.assertFalse((self.root / shortcut.NAME).exists())
        self.assertEqual(len(list((self.root / shortcut.CACHE).iterdir())), 1)
        with mock.patch.object(shortcut, "icon_bytes", return_value=b"icon"), \
                mock.patch.object(shortcut, "powershell", side_effect=self.save):
            self.assertEqual(self.create(), self.root / shortcut.NAME)

    def test_non_windows_does_not_create_files_or_import_qt(self):
        with mock.patch.object(shortcut.sys, "platform", "darwin"), \
                mock.patch.object(shortcut, "icon_bytes") as icon, \
                mock.patch.object(shortcut, "powershell") as shell:
            self.assertIsNone(shortcut.ensure(self.root))
        icon.assert_not_called()
        shell.assert_not_called()
        self.assertFalse((self.root / shortcut.CACHE).exists())

    def test_optional_shortcut_failure_is_logged_without_stopping_startup(self):
        for error in (PermissionError("read-only"), OSError("COM unavailable"),
                      subprocess.CalledProcessError(1, "powershell")):
            with self.subTest(error=error), mock.patch.object(shortcut, "create", side_effect=error), \
                    contextlib.redirect_stderr(io.StringIO()) as log:
                self.assertIsNone(shortcut.ensure(self.root))
                self.assertIn("start.bat", log.getvalue())
                self.assertIn(type(error).__name__, log.getvalue())

class PowershellTest(unittest.TestCase):
    def test_unicode_quotes_and_different_drives_stay_outside_the_script(self):
        payload = {"target": r"D:\한글 Python\pythonw.exe", "workdir": r"E:\공부 ' & $ ` [ ] , 폴더",
                   "arguments": subprocess.list2cmdline([r'E:\공부 "인용"\start.pyw'])}
        with mock.patch.dict(os.environ, {"SystemRoot": r"C:\Windows"}), \
                mock.patch.object(subprocess, "CREATE_NO_WINDOW", 0x08000000, create=True), \
                mock.patch.object(subprocess, "run") as run:
            shortcut.powershell(shortcut.SCRIPT, payload)
        args, kwargs = run.call_args
        command = args[0]
        self.assertEqual(base64.b64decode(command[-1]).decode("utf-16-le"), shortcut.SCRIPT)
        self.assertEqual(command[1:4], ["-NoProfile", "-NonInteractive", "-EncodedCommand"])
        self.assertEqual(json.loads(kwargs["env"][shortcut.PAYLOAD]), payload)
        self.assertNotIn("shell", kwargs)
        self.assertEqual(kwargs["creationflags"], 0x08000000)
        self.assertTrue(kwargs["check"])
        self.assertEqual(kwargs["timeout"], 15)

    def test_generated_paths_are_gitignored(self):
        root = Path(__file__).resolve().parents[1]
        paths = [shortcut.NAME, shortcut.CACHE + "/icon.ico"]
        result = subprocess.run(["git", "check-ignore", "--", *paths], cwd=root,
                                check=True, capture_output=True)
        self.assertEqual(len(result.stdout.splitlines()), 2)


if __name__ == "__main__":
    unittest.main()
