# -*- coding: utf-8 -*-
"""R 아이콘의 ICO와 Windows 바로가기 속성·실행을 확인함."""
import json
from pathlib import Path
import struct
import sys
import tempfile
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
            for flags in (0x100, 0x101):  # SHGFI_ICON의 큰 아이콘과 작은 아이콘을 조회함. 화살표 덧그림은 요청하지 않음.
                info = FileInfo()
                self.assertTrue(shell(str(link), 0, ctypes.byref(info), ctypes.sizeof(info), flags))
                self.assertTrue(info.hIcon)
                try:
                    actual = QImage.fromHICON(int(info.hIcon))
                    self.assertFalse(actual.isNull())
                    expected = QIcon(str(source)).pixmap(actual.size(), 1.0).toImage()
                    self.assertEqual(actual.size(), expected.size())
                    for x in range(2, 7):
                        for y in range(2, 7):
                            spot = (actual.width() * x // 8, actual.height() * y // 8)
                            want, found = expected.pixelColor(*spot), actual.pixelColor(*spot)
                            self.assertEqual(want.alpha(), 255)
                            self.assertLessEqual(max(abs(a - b) for a, b in zip(want.getRgb(), found.getRgb())), 8)
                finally:
                    self.assertTrue(destroy(info.hIcon))
        finally:
            ole.CoUninitialize()

    def test_native_shortcut_properties_and_pythonw_launch(self):
        with tempfile.TemporaryDirectory(prefix="study 한글 ' & $ [ , ") as temporary:
            root = Path(temporary).resolve()
            start = root / "start.pyw"
            start.write_text(
                "import json, os, sys\nfrom pathlib import Path\n"
                "result = Path(__file__).with_name('ran.tmp')\n"
                "result.write_text(json.dumps({'cwd': os.getcwd(), 'argv': sys.argv, "
                "'python': sys.executable, 'prefix': sys.prefix}), encoding='utf-8')\n"
                "result.replace(result.with_name('ran.json'))\n",
                encoding="utf-8")
            link = shortcut.create(root)
            self.assertEqual(link, root / shortcut.NAME)
            self.assertEqual(link.read_bytes()[:4], b"L\x00\x00\x00")
            read = shortcut.powershell(r"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding
$p = $env:STUDY_SHORTCUT_JSON | ConvertFrom-Json
$link = (New-Object -ComObject WScript.Shell).CreateShortcut($p.link)
@{target=$link.TargetPath; arguments=$link.Arguments; workdir=$link.WorkingDirectory;
  icon=$link.IconLocation} | ConvertTo-Json -Compress
""", {"link": str(link)})
            properties = json.loads(read.stdout.decode("utf-8-sig"))
            pythonw = Path(sys.executable).with_name("pythonw.exe")
            self.assertEqual(Path(properties["target"]), pythonw)
            self.assertEqual(properties["arguments"], shortcut.subprocess.list2cmdline([str(start)]))
            self.assertEqual(Path(properties["workdir"]), root)
            self.assertEqual(properties["icon"], str(root / shortcut.CACHE / "icon.ico") + ",0")
            self.assertFalse(QIcon(str(root / shortcut.CACHE / "icon.ico")).isNull())
            self.check_shell_icon(link, root / shortcut.CACHE / "icon.ico")
            original = link.read_bytes()
            self.assertIsNone(shortcut.create(root))
            self.assertEqual(link.read_bytes(), original)
            shortcut.powershell(r"""
$ErrorActionPreference = 'Stop'
$p = $env:STUDY_SHORTCUT_JSON | ConvertFrom-Json
Start-Process -FilePath $p.link -Wait
""", {"link": str(link)})
            result = root / "ran.json"
            self.assertTrue(result.exists(), "pythonw 실행 기록이 없습니다")
            actual = json.loads(result.read_text(encoding="utf-8"))
            self.assertEqual(Path(actual["cwd"]), root)
            self.assertEqual(actual["argv"], [str(start)])
            self.assertEqual(Path(actual["python"]), pythonw)
            self.assertEqual(Path(actual["prefix"]), Path(sys.prefix))


if __name__ == "__main__":
    unittest.main()
