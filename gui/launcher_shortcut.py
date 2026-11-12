# -*- coding: utf-8 -*-
"""Windows 첫 실행 뒤 프로그램 폴더에 R 아이콘 바로가기를 만듦."""
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile

NAME = "프로그래밍 스터디.lnk"
CACHE = ".study-launcher"


def save_shortcut(payload):
    """IShellLinkW와 IPersistFile로 경로를 유니코드 그대로 저장함."""
    import ctypes as ct
    from ctypes import wintypes as wt
    import uuid

    class GUID(ct.Structure):
        _fields_ = [("data1", wt.DWORD), ("data2", wt.WORD), ("data3", wt.WORD), ("data4", ct.c_ubyte * 8)]

    def guid(value):
        return GUID.from_buffer_copy(uuid.UUID(value).bytes_le)

    def check(result):
        if result < 0:
            raise ct.WinError(result)

    def method(pointer, index, result, *arguments):
        table = ct.cast(pointer, ct.POINTER(ct.POINTER(ct.c_void_p))).contents
        return ct.WINFUNCTYPE(result, ct.c_void_p, *arguments)(table[index])

    ole = ct.WinDLL("ole32")
    ole.CoInitializeEx.argtypes, ole.CoInitializeEx.restype = [ct.c_void_p, wt.DWORD], ct.c_long
    ole.CoUninitialize.argtypes, ole.CoUninitialize.restype = [], None
    ole.CoCreateInstance.argtypes = [ct.POINTER(GUID), ct.c_void_p, wt.DWORD, ct.POINTER(GUID), ct.POINTER(ct.c_void_p)]
    ole.CoCreateInstance.restype = ct.c_long
    initialized = ole.CoInitializeEx(None, 2)
    if initialized != -2147417850:  # RPC_E_CHANGED_MODE이면 이미 설정된 apartment를 사용함.
        check(initialized)
    link, persist = ct.c_void_p(), ct.c_void_p()
    try:
        clsid = guid("00021401-0000-0000-c000-000000000046")
        iid = guid("000214f9-0000-0000-c000-000000000046")
        check(ole.CoCreateInstance(ct.byref(clsid), None, 1, ct.byref(iid), ct.byref(link)))
        # IShellLinkW의 SetPath·SetArguments·SetWorkingDirectory·SetDescription임.
        for index, value in ((20, payload["target"]), (11, payload["arguments"]),
                             (9, payload["workdir"]), (7, "프로그래밍 스터디")):
            check(method(link, index, ct.c_long, wt.LPCWSTR)(link, value))
        check(method(link, 17, ct.c_long, wt.LPCWSTR, ct.c_int)(link, payload["icon"], 0))
        iid = guid("0000010b-0000-0000-c000-000000000046")
        check(method(link, 0, ct.c_long, ct.POINTER(GUID), ct.POINTER(ct.c_void_p))
              (link, ct.byref(iid), ct.byref(persist)))
        saved = method(persist, 6, ct.c_long, wt.LPCWSTR, wt.BOOL)(persist, payload["link"], True)
        check(saved)
        if saved != 0:
            raise OSError("바로가기 파일을 저장하지 못했습니다.")
    finally:
        for pointer in (persist, link):
            if pointer:
                method(pointer, 2, wt.ULONG)(pointer)
        if initialized >= 0:
            ole.CoUninitialize()


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
        save_shortcut({"link": str(pending), "target": str(pythonw),
                            "arguments": subprocess.list2cmdline([str(start)]),
                            "workdir": str(root), "icon": str(icon)})
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
