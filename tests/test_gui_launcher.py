# -*- coding: utf-8 -*-
"""R 아이콘의 ICO와 Windows 바로가기 속성·실행을 확인함."""
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import time
import unittest
from unittest import mock

from tests import guikit
from PyQt6.QtCore import QLockFile
from PyQt6.QtGui import QIcon, QImage

from gui import app, icon, launcher_shortcut as shortcut


class IconFileTest(unittest.TestCase):
    def test_ico_directory_contains_the_original_pixels_at_all_sizes(self):
        data = shortcut.icon_bytes()
        self.assertEqual(struct.unpack_from("<HHH", data), (0, 1, len(icon.SIZES)))
        offset = 6 + 16 * len(icon.SIZES)
        for index, size in enumerate(icon.SIZES):
            w, h, colors, reserved, planes, bits, length, start = struct.unpack_from("<BBBBHHII", data, 6 + 16 * index)
            self.assertEqual((w or 256, h or 256, colors, reserved, planes, bits, start),
                             (size, size, 0, 0, 1, 32, offset))
            frame = QImage.fromData(data[start:start + length], "PNG")
            expected = icon.pixmap(size).toImage().convertToFormat(frame.format())
            self.assertEqual(frame, expected)
            offset += length
        self.assertEqual(offset, len(data))
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "icon.ico"
            target.write_bytes(data)
            loaded = QIcon(str(target))
            self.assertFalse(loaded.isNull())
            self.assertEqual(sorted(size.width() for size in loaded.availableSizes()), list(icon.SIZES))


class StartupTest(unittest.TestCase):
    def test_app_creates_shortcut_after_the_instance_lock_and_before_boot(self):
        events = []
        lock = mock.Mock(spec=QLockFile)
        lock.tryLock.return_value = True
        window = mock.Mock()
        window.restart = False
        window.boot.side_effect = lambda: events.append("boot")
        with mock.patch.object(app, "QApplication", return_value=mock.Mock(exec=mock.Mock(return_value=0))), \
                mock.patch.object(app, "QSettings"), mock.patch.object(app, "QLockFile", return_value=lock), \
                mock.patch.object(app.theme, "apply"), mock.patch.object(app.icon, "install"), \
                mock.patch.object(app, "korean"), mock.patch.object(app.errors, "install"), \
                mock.patch.object(app, "stop_servers_on_hangup"), \
                mock.patch.object(app, "MainWindow", return_value=window), \
                mock.patch.object(shortcut, "ensure", side_effect=lambda root: events.append(root)) as ensure, \
                mock.patch.object(app.MessageDialog, "exec"):
            self.assertEqual(app.main([]), 0)
            self.assertEqual(events, [app.study.ROOT, "boot"])
            lock.unlock.assert_called_once_with()
            ensure.reset_mock()
            window.reset_mock()
            lock.tryLock.return_value = False
            self.assertEqual(app.main([]), 1)
            ensure.assert_not_called()
            window.boot.assert_not_called()


@unittest.skipUnless(sys.platform == "win32", "Windows의 COM·Shell 실행에서 확인합니다")
class NativeShortcutTest(unittest.TestCase):
    def check_shell_icon(self, link, source):
        import ctypes
        from ctypes import wintypes

        class FileInfo(ctypes.Structure):
            _fields_ = [("hIcon", wintypes.HICON), ("iIcon", ctypes.c_int), ("dwAttributes", wintypes.DWORD),
                        ("szDisplayName", wintypes.WCHAR * 260), ("szTypeName", wintypes.WCHAR * 80)]

        shell = ctypes.windll.shell32.SHGetFileInfoW
        shell.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, ctypes.POINTER(FileInfo), wintypes.UINT, wintypes.UINT]
        shell.restype = ctypes.c_size_t
        destroy = ctypes.windll.user32.DestroyIcon
        destroy.argtypes = [wintypes.HICON]
        destroy.restype = wintypes.BOOL
        ole = ctypes.windll.ole32
        ole.CoInitialize.argtypes = [ctypes.c_void_p]
        ole.CoInitialize.restype = ctypes.c_long
        self.assertGreaterEqual(ole.CoInitialize(None), 0)
        try:
            location = FileInfo()
            self.assertTrue(shell(str(link), 0, ctypes.byref(location), ctypes.sizeof(location), 0x1000))
            self.assertEqual(Path(location.szDisplayName.strip('"')), source)
            self.assertEqual(location.iIcon, 0)
            for flags in (0x100, 0x101):  # SHGFI_ICON의 큰 아이콘과 작은 아이콘을 조회함.
                with self.subTest(icon_flags=flags):
                    self.check_icon_pixels(shell, destroy, FileInfo, link, source, flags)
        finally:
            ole.CoUninitialize()

    def check_icon_pixels(self, shell, destroy, FileInfo, link, source, flags):
        import ctypes
        info = FileInfo()
        self.assertTrue(shell(str(link), 0, ctypes.byref(info), ctypes.sizeof(info), flags))
        self.assertTrue(info.hIcon)
        try:
            actual = QImage.fromHICON(int(info.hIcon))
            self.assertFalse(actual.isNull())
            reference = FileInfo()
            # Shell이 LNK에 붙이는 화살표를 원본 ICO에도 같은 API로 붙여 비교함.
            self.assertTrue(shell(str(source), 0, ctypes.byref(reference), ctypes.sizeof(reference), flags | 0x8000))
            self.assertTrue(reference.hIcon)
            try:
                expected = QImage.fromHICON(int(reference.hIcon))
            finally:
                self.assertTrue(destroy(reference.hIcon))
            self.assertFalse(expected.isNull())
            self.assertEqual(actual.size(), expected.size())
            folder = getattr(self, "capture_directory", None)
            if folder:
                self.assertTrue(actual.save(str(folder / ("shortcut-shell-%s.png" % flags))))
                self.assertTrue(expected.save(str(folder / ("shortcut-source-%s.png" % flags))))
            for x in range(actual.width()):
                for y in range(actual.height()):
                    want, found = expected.pixelColor(x, y), actual.pixelColor(x, y)
                    delta = max(abs(a - b) for a, b in zip(want.getRgb(), found.getRgb()))
                    self.assertLessEqual(delta, 8, (flags, x, y, want.getRgb(), found.getRgb()))
        finally:
            self.assertTrue(destroy(info.hIcon))

    def test_native_shortcut_properties_and_pythonw_launch(self):
        with tempfile.TemporaryDirectory(prefix="study 한글 ' & $ [ , ") as temporary:
            root = Path(temporary).resolve()
            start = root / "start.pyw"
            start.write_text(
                "import json, os, sys\nfrom pathlib import Path\n"
                "result = Path(__file__).with_name('ran.tmp')\n"
                "data = {'cwd': os.getcwd(), 'argv': sys.argv, 'python': sys.executable, 'prefix': sys.prefix}\n"
                "os.chdir(os.path.dirname(sys.executable))\n"
                "result.write_text(json.dumps(data), encoding='utf-8')\n"
                "result.replace(result.with_name('ran.json'))\n",
                encoding="utf-8")
            link = shortcut.create(root)
            self.assertEqual(link, root / shortcut.NAME)
            self.assertEqual(link.read_bytes()[:4], b"L\x00\x00\x00")
            pythonw = Path(sys.executable).with_name("pythonw.exe")
            self.assertIn(str(start).encode("utf-16-le"), link.read_bytes())
            self.assertFalse(QIcon(str(root / shortcut.CACHE / "icon.ico")).isNull())
            self.check_shell_icon(link, root / shortcut.CACHE / "icon.ico")
            original = link.read_bytes()
            self.assertIsNone(shortcut.create(root))
            self.assertEqual(link.read_bytes(), original)
            os.startfile(str(link))
            result = root / "ran.json"
            deadline = time.monotonic() + 10
            while not result.exists() and time.monotonic() < deadline:
                time.sleep(0.05)
            self.assertTrue(result.exists(), "pythonw 실행 기록이 없습니다")
            actual = json.loads(result.read_text(encoding="utf-8"))
            self.assertEqual(Path(actual["cwd"]), root)
            self.assertEqual(actual["argv"], [str(start)])
            self.assertEqual(Path(actual["python"]), pythonw)
            self.assertEqual(Path(actual["prefix"]), Path(sys.prefix))


if __name__ == "__main__":
    unittest.main()
