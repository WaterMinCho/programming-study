# -*- coding: utf-8 -*-
"""Windows 첫 실행 뒤 프로그램 폴더에 R 아이콘 바로가기를 만듦."""
import base64
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile

NAME = "프로그래밍 스터디.lnk"
CACHE = ".study-launcher"
PAYLOAD = "STUDY_SHORTCUT_JSON"
SCRIPT = r"""
$ErrorActionPreference = 'Stop'
$p = $env:STUDY_SHORTCUT_JSON | ConvertFrom-Json
$shell = New-Object -ComObject WScript.Shell
$link = $shell.CreateShortcut($p.link)
$link.TargetPath = $p.target
$link.Arguments = $p.arguments
$link.WorkingDirectory = $p.workdir
$link.IconLocation = $p.icon
$link.Description = '프로그래밍 스터디'
$link.Save()
$saved = $shell.CreateShortcut($p.link)
foreach ($pair in @(@('TargetPath', 'target'), @('Arguments', 'arguments'),
                    @('WorkingDirectory', 'workdir'), @('IconLocation', 'icon'))) {
    if ($saved.($pair[0]) -ne $p.($pair[1])) {
        throw ('Shortcut property was not saved: ' + $pair[0] + '; ' +
               (@{expected=$p.($pair[1]); actual=$saved.($pair[0])} | ConvertTo-Json -Compress))
    }
}
"""


def powershell(script, payload):
    """고정 명령과 경로 데이터를 나누고 콘솔 창 없이 실행함."""
    command = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    system = Path(os.environ["SystemRoot"])
    executable = system / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    return subprocess.run([str(executable), "-NoProfile", "-NonInteractive", "-EncodedCommand", command],
                          env=dict(os.environ, **{PAYLOAD: json.dumps(payload, ensure_ascii=True)}),
                          stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          creationflags=subprocess.CREATE_NO_WINDOW, timeout=15, check=True)


def icon_bytes():
    """기존 그림의 크기별 PNG를 ICO 디렉터리와 함께 저장할 바이트로 묶음."""
    from PyQt6.QtCore import QBuffer, QIODevice
    from gui.icon import SIZES, pixmap

    entries, images = [], []
    offset = 6 + 16 * len(SIZES)
    for size in SIZES:
        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        if not pixmap(size).save(buffer, "PNG"):
            raise OSError("프로그램 아이콘을 만들지 못했습니다.")
        data = bytes(buffer.data())
        entries.append(struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(data), offset))
        images.append(data)
        offset += len(data)
    return struct.pack("<HHH", 0, 1, len(SIZES)) + b"".join(entries + images)


def create(root, executable=None):
    """현재 화면을 실행한 파이썬 옆의 pythonw로 여는 바로가기를 만듦. 기존 파일은 건드리지 않음."""
    if sys.platform != "win32":
        return None
    root = Path(root).resolve()
    link = root / NAME
    if os.path.lexists(link):
        return None
    pythonw = Path(os.path.abspath(executable or sys.executable)).with_name("pythonw.exe")
    start = root / "start.pyw"
    if not pythonw.is_file() or not start.is_file():
        raise FileNotFoundError("바로가기에 필요한 pythonw.exe 또는 start.pyw를 찾지 못했습니다.")
    cache = root / CACHE
    cache.mkdir(exist_ok=True)
    icon = cache / "icon.ico"
    with tempfile.TemporaryDirectory(dir=cache) as temporary:
        temporary = Path(temporary)
        image = temporary / "icon.ico"
        image.write_bytes(icon_bytes())
        os.replace(image, icon)
        pending = temporary / NAME
        powershell(SCRIPT, {"link": str(pending), "target": str(pythonw),
                            "arguments": subprocess.list2cmdline([str(start)]),
                            "workdir": str(root), "icon": str(icon) + ",0"})
        # Windows의 rename은 목적지 파일이 먼저 생겼어도 덮어쓰지 않음.
        try:
            os.rename(pending, link)
        except FileExistsError:
            return None
    return link


def ensure(root):
    """바로가기 실패가 학습 화면의 실행을 막지 않게 기록함. 다음 실행 때 다시 시도함."""
    try:
        return create(root)
    except Exception as error:
        if sys.stderr:
            print("실행 바로가기를 만들지 못했습니다. start.bat으로 계속 실행할 수 있습니다. %s: %s"
                  % (type(error).__name__, error), file=sys.stderr)
        return None
