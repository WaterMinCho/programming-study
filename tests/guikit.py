# -*- coding: utf-8 -*-
"""화면 테스트들이 같이 쓰는 도우미. 테스트 모듈이 아니라서 discover 가 모으지 않음. `from tests import guikit` 로 가져옴.

가져오는 쪽에서 QApplication 을 하나 만들고 테마를 입히며 움직임을 끔. PyQt6 가 없으면 SkipTest 를 일으켜서
이 모듈을 가져오는 테스트 모듈이 통째로 건너뛰어짐.
"""
import os
import sys
import time
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("STUDY_NODE_PROBE", "0")  # 로그인 셸로 node 를 찾지 않음

try:
    from PyQt6.QtCore import QEventLoop, Qt, QTimer, qInstallMessageHandler
    from PyQt6.QtTest import QTest
    from PyQt6.QtWidgets import QApplication
except ImportError:
    raise unittest.SkipTest("PyQt6 가 설치돼 있지 않아 화면 테스트를 건너뜁니다")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from gui import motion, theme  # noqa: E402

NOISE = ("propagateSizeHints", "Populating font family aliases")  # offscreen 플랫폼이 창을 띄울 때마다 찍는 안내
qInstallMessageHandler(lambda mode, context, text: None if any(n in text for n in NOISE) else print(text, file=sys.stderr))
APP = QApplication.instance() or QApplication(sys.argv[:1])
theme.apply(APP)
motion.enabled = False  # 움직임은 그것을 보는 테스트에서만 켬
LEFT = Qt.MouseButton.LeftButton
SHIFT = Qt.KeyboardModifier.ShiftModifier
CTRL = Qt.KeyboardModifier.ControlModifier
SYNTAX = ("keyword", "def", "builtin", "string", "comment", "number", "decorator", "self", "blank")  # 문법 색칠이 나누는 종류


def pump(ms=30):
    """이벤트 루프를 ms 동안 돌림."""
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def wait_until(predicate, timeout=30.0):
    """predicate 가 참이 될 때까지 이벤트 루프를 돌림. timeout 은 테스트가 멈추지 않게 하는 상한이지 단언이 아님."""
    start = time.monotonic()
    while not predicate():
        if time.monotonic() - start > timeout:
            raise TimeoutError("화면이 기다리던 상태가 되지 않았습니다")
        pump(20)


def click(widget):
    QTest.mouseClick(widget, LEFT)
    pump()


def painted(editor, line):
    """문법 색칠이 한 줄에 입힌 조각을 (글, 종류)로 돌려줌. 색을 입히지 않은 글은 빠짐."""
    kinds = {theme.EDITOR[name]: name for name in SYNTAX}
    block = editor.document().findBlockByNumber(line)
    raw = block.text().encode("utf-16-le")  # Qt 의 위치는 UTF-16 단위
    return [(raw[2 * part.start:2 * (part.start + part.length)].decode("utf-16-le"), kinds[part.format.foreground().color().name()])
            for part in block.layout().formats()]
