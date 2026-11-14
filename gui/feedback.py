# -*- coding: utf-8 -*-
"""문의 URL에 허용한 환경값만 넣음. 답안·계정·로그는 읽지 않음."""
import builtins
import datetime
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
from urllib.parse import urlencode
from urllib.error import HTTPError


ISSUE_URL = "https://github.com/WaterMinCho/programming-study/issues/new"
CHOOSE_URL = ISSUE_URL + "/choose"
ROOT = Path(__file__).resolve().parent.parent
UNKNOWN = "미확인"
BUILTIN_EXCEPTION_NAMES = frozenset(
    name for name, kind in vars(builtins).items()
    if isinstance(kind, type) and kind.__module__ == "builtins" and issubclass(kind, BaseException)
)
PROJECT_EXCEPTION_NAMES = frozenset({
    "SessionError", "GitError", "Stop", "CollectionError", "DevError", "CheckError", "BankError",
    "MockError", "WebError", "AlreadyReceived", "RecordError", "OutputLimit", "GenError",
    "JourneyError", "AiBankError", "Retry", "AiError", "GuideError", "EngineUnavailable",
})
EXCEPTION_NAMES = BUILTIN_EXCEPTION_NAMES | PROJECT_EXCEPTION_NAMES
EXCEPTION_NAMES |= frozenset({"HTTPError", "URLError", "JSONDecodeError", "TimeoutExpired", "CalledProcessError"})
PAGE_KEYS = (
    "start", "hub", "home", "round_page", "result_page", "wrong_page",
    "journey_map", "journey_page", "web_home", "web_mission", "web_drill", "web_learn",
    "ai_home", "ai_lesson", "ai_learn", "ai_note", "ai_revisit", "ai_quiz", "ai_mock",
)
# 추적 중인 공통 실행·화면 소스만 허용함. 사용자 파일과 새 경로는 자동으로 추가하지 않음.
PROGRAM_PATHS = {
    "bootstrap.py", "gitflow.py", "study.py", "start.pyw",
    "gui/app.py", "gui/window.py", "gui/worker.py", "gui/theme.py", "gui/kit.py",
    "gui/settings_menu.py", "gui/errors.py", "gui/dialogs.py", "gui/feedback.py",
}


def _read(probe):
    try:
        return probe()
    except Exception:
        return UNKNOWN


def _version(value):
    return value if isinstance(value, str) and re.fullmatch(r"[0-9]{1,4}(?:\.[0-9]{1,6}){1,3}", value) else UNKNOWN


def _number(value, low, high):
    if type(value) in (int, float) and low <= value <= high:
        return "%g" % value
    return UNKNOWN


def commit():
    """정해진 Git 명령만 짧은 대기 시간으로 실행함."""
    try:
        if not (ROOT / ".git").exists():
            return UNKNOWN
        env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        env["GIT_CEILING_DIRECTORIES"] = str(ROOT.parent)
        result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                                text=True, timeout=0.5, check=True,
                                env=env,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        value = result.stdout.strip()
        return value if re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", value) else UNKNOWN
    except (OSError, subprocess.SubprocessError, UnicodeError):
        return UNKNOWN


def _os_version():
    if sys.platform == "win32":
        value = sys.getwindowsversion()
        return "%d.%d.%d" % (value.major, value.minor, value.build)
    if sys.platform == "darwin":
        return _version(platform.mac_ver()[0])
    return UNKNOWN


def _screen_key(window):
    current = window.pages.currentWidget()
    for key in PAGE_KEYS:
        if current is not None and current is getattr(window, key, None):
            return key
    career = getattr(window, "career", None)
    for key in ("roadmap", "magazine"):
        if current is not None and current is getattr(career, key, None):
            return "career_" + key
    return UNKNOWN


def environment(window=None):
    """실행 환경과 화면의 숫자·고정 선택값만 읽음. 조회 실패는 미확인으로 남김."""
    values = {"OS": {"win32": "Windows", "darwin": "macOS", "linux": "Linux"}.get(sys.platform, UNKNOWN),
              "OS_version": _version(_read(_os_version)), "Python": ".".join(str(n) for n in sys.version_info[:3]),
              "PyQt": UNKNOWN, "Qt": UNKNOWN, "commit": commit(), "screen": UNKNOWN,
              "window": UNKNOWN, "DPR": UNKNOWN, "DPI": UNKNOWN,
              "text": UNKNOWN, "theme": UNKNOWN, "scheme": UNKNOWN}
    try:
        from PyQt6.QtCore import PYQT_VERSION_STR, qVersion
        from PyQt6.QtWidgets import QApplication
        values["PyQt"], values["Qt"] = _version(PYQT_VERSION_STR), _version(qVersion())
        app = QApplication.instance()
        if app is not None:
            if window is None:
                window = app.activeWindow()
                owner = window
                while owner is not None:
                    if hasattr(owner, "pages"):
                        window = owner
                        break
                    owner = owner.parentWidget()
                else:
                    window = next((item for item in app.topLevelWidgets() if hasattr(item, "pages")), window)
            screen = window.screen() if window is not None else app.primaryScreen()
            if screen is not None:
                values["DPR"] = _number(_read(screen.devicePixelRatio), 0.25, 16)
                values["DPI"] = _number(_read(screen.logicalDotsPerInch), 24, 2000)
            if window is not None:
                values["screen"] = _read(lambda: _screen_key(window))
                width = _number(_read(window.width), 1, 65535)
                height = _number(_read(window.height), 1, 65535)
                if UNKNOWN not in (width, height):
                    values["window"] = width + "x" + height
    except Exception:
        pass
    try:
        from gui import theme
        for key, choices in (("text", ("normal", "large", "larger")),
                             ("mode", ("system", "light", "dark")), ("scheme", ("light", "dark"))):
            value = theme.state.get(key)
            values["theme" if key == "mode" else key] = value if value in choices else UNKNOWN
    except Exception:
        pass
    return values


def error_details(error=None, tb=None):
    """예외 문자열·프레임 변수 대신 종류·HTTP 코드·허용한 소스 위치만 고름."""
    if not isinstance(error, BaseException):
        return {}
    name = type(error).__name__
    values = {"exception": name if name in EXCEPTION_NAMES else "OtherError"}
    code = _read(lambda: error.code) if isinstance(error, HTTPError) else None
    if type(code) is int and 100 <= code <= 599:
        values["status"] = str(code)
    while tb is not None:
        try:
            path = Path(tb.tb_frame.f_code.co_filename).resolve()
            relative = path.relative_to(ROOT).as_posix()
            if (relative in PROGRAM_PATHS
                    and type(tb.tb_lineno) is int and 0 < tb.tb_lineno < 10000000):
                values["location"] = "%s:%d" % (relative, tb.tb_lineno)
        except (OSError, ValueError, RuntimeError):
            pass
        tb = tb.tb_next
    return values


def issue_url(window=None, *, error=None, tb=None):
    observed_at = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds") if isinstance(error, BaseException) else None
    values = environment(window)
    details = error_details(error, tb)
    if details:
        details["error_observed_at_utc"] = observed_at
    values.update(details)
    return ISSUE_URL + "?" + urlencode({"template": "trouble.yml", "env": "\n".join(
        "%s: %s" % item for item in values.items())})
