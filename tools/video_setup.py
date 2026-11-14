"""명시한 준비 동작 뒤 기존 Qt 구성을 고정하고 재생기만 추가함."""
from __future__ import annotations

from importlib import metadata
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import threading
import time

CORE_PACKAGES = ("PyQt6", "PyQt6-Qt6", "PyQt6-sip")
ENGINE_PACKAGES = {"pyqt6-webengine", "pyqt6-webengine-qt6"}
# 별도 버전 체계는 확인한 코어와 두 엔진 패키지의 조합만 연결함.
CONFIRMED_ENGINE_VERSIONS = {"6.12.0": "6.140.0"}


def core_versions():
    """설치한 배포 메타데이터만 읽으며 WebEngine을 가져오지 않음."""
    return {name: metadata.version(name) for name in CORE_PACKAGES}


def _minor(version):
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", version)
    if not match:
        raise ValueError("설치된 Qt 버전과 맞는 재생기를 확인하지 못했습니다.")
    return tuple(map(int, match.groups()[:2]))


def _normal(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def _engine_versions(core):
    minor = _minor(core["PyQt6-Qt6"])
    if minor[0] != 6 or _minor(core["PyQt6"]) != minor:
        raise ValueError("현재 PyQt와 Qt 버전이 맞지 않습니다. YouTube에서 영상을 열어 주세요.")
    if core["PyQt6-Qt6"] in CONFIRMED_ENGINE_VERSIONS:
        return dict.fromkeys(ENGINE_PACKAGES, CONFIRMED_ENGINE_VERSIONS[core["PyQt6-Qt6"]])
    if minor > (6, 11):
        raise ValueError("현재 Qt와 재생기의 조합을 확인하지 못했습니다. YouTube에서 열어 주세요.")
    return {"pyqt6-webengine": None, "pyqt6-webengine-qt6": core["PyQt6-Qt6"]}


def checked_plan(report, core):
    """pip의 예정 작업에 기존 Qt나 관계없는 패키지가 있으면 설치를 거절함."""
    minor = _minor(core["PyQt6-Qt6"])
    versions = _engine_versions(core)
    packages = {}
    for item in report["install"]:
        entry = item["metadata"]
        name, version = _normal(entry["name"]), entry["version"]
        if name not in ENGINE_PACKAGES or name in packages:
            raise ValueError("기존 Qt 구성을 바꾸지 않고 재생기를 설치할 수 없습니다.")
        expected = versions[name]
        if (expected is not None and version != expected) or (expected is None and _minor(version) != minor):
            raise ValueError("기존 Qt 구성에 맞는 재생기를 찾지 못했습니다.")
        packages[name] = version
    return [f"{name}=={version}" for name, version in sorted(packages.items())]


def _run(command, cancel, applying=False):
    """계획 확인은 취소하고 설치 시작 뒤에는 패키지 쓰기가 끝날 때까지 기다림."""
    with tempfile.TemporaryFile() as output:
        process = subprocess.Popen(command, stdout=output, stderr=subprocess.STDOUT)
        started = time.monotonic()
        try:
            while True:
                try:
                    process.wait(timeout=0.1)
                    break
                except subprocess.TimeoutExpired:
                    if not applying and (cancel.is_set() or time.monotonic() - started >= 360):
                        process.terminate()
                        try:
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait()
                        break
            return subprocess.CompletedProcess(command, process.returncode)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()


def _lock_path():
    key = hashlib.sha256(os.path.realpath(sys.prefix).encode()).hexdigest()[:20]
    return Path(tempfile.gettempdir()) / ("rokey-video-" + key + ".lock")


def _acquire_lock(path):
    """삭제하지 않는 한 바이트 파일을 잠그고 프로세스 종료 때 OS가 잠금을 해제함."""
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        if os.fstat(descriptor).st_size == 0:
            os.write(descriptor, b"\0")
        os.lseek(descriptor, 0, os.SEEK_SET)
        if sys.platform == "win32":
            import msvcrt
            msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _import_probe():
    """앱을 만들지 않는 별도 프로세스에서 라이브러리 로드를 확인함."""
    result = subprocess.run([sys.executable, "-I", "-c",
                             "from PyQt6.QtWebEngineWidgets import QWebEngineView"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
    return result.returncode == 0


def install(cancel=None, *, runner=None, versions=None, import_probe=None):
    """준비 버튼을 누른 뒤 작업 스레드에서 호출함. 성공하면 재시작 결과를 돌려줌."""
    cancel = cancel if cancel is not None else threading.Event()
    runner, versions = runner or _run, versions or core_versions
    import_probe = import_probe or _import_probe
    if cancel.is_set():
        return {"status": "cancelled", "ok": False, "restart": False}
    # 다른 준비 작업과 겹치지 않게 실행 환경마다 잠금 하나를 소유함.
    try:
        descriptor = _acquire_lock(_lock_path())
    except OSError:
        return {"status": "error", "ok": False, "restart": False,
                "message": "진행 중인 설치가 끝난 뒤 다시 시도해 주세요."}
    try:
        core = versions()
        minor = _minor(core["PyQt6-Qt6"])
        engine_versions = _engine_versions(core)
        with tempfile.TemporaryDirectory(prefix="rokey-video-") as folder:
            constraints, report = Path(folder) / "constraints.txt", Path(folder) / "report.json"
            constraints.write_text("".join(f"{name}=={value}\n" for name, value in core.items()), encoding="utf-8")
            base = [sys.executable, "-m", "pip", "--isolated", "install", "--disable-pip-version-check",
                    "--no-input", "--only-binary=:all:", "--constraint", str(constraints)]
            requirement = f">={minor[0]}.{minor[1]},<{minor[0]}.{minor[1] + 1}"
            requirements = [name + ("==" + engine_versions[_normal(name)]
                                    if engine_versions[_normal(name)] is not None else requirement)
                            for name in ("PyQt6-WebEngine", "PyQt6-WebEngine-Qt6")]
            probe = runner(base + ["--dry-run", "--report", str(report)] + requirements, cancel)
            if cancel.is_set():
                return {"status": "cancelled", "ok": False, "restart": False}
            if probe.returncode:
                raise ValueError("현재 Qt와 호환되는 재생기를 확인하지 못했습니다.")
            plan = checked_plan(json.loads(report.read_text(encoding="utf-8")), core)
            if versions() != core:
                raise ValueError("설치 중 Qt 구성이 바뀌었습니다.")
            if cancel.is_set():
                return {"status": "cancelled", "ok": False, "restart": False}
            if plan:
                result = runner(base + ["--no-deps"] + plan, cancel, applying=True)
                if result.returncode:
                    raise ValueError("재생기를 설치하지 못했습니다.")
            if versions() != core:
                raise ValueError("다른 작업에서 Qt 구성을 바꿨습니다.")
        if cancel.is_set():
            return {"status": "cancelled", "ok": False, "restart": False, "installed": True}
        try:
            loadable = import_probe()
        except (OSError, subprocess.SubprocessError):
            loadable = False
        if not loadable:
            return {"status": "error", "ok": False, "restart": False,
                    "message": "앱 내 재생기를 불러오지 못했습니다."}
        if versions() != core:
            raise ValueError("확인 중 Qt 구성이 바뀌었습니다.")
        if cancel.is_set():
            return {"status": "cancelled", "ok": False, "restart": False, "installed": True}
        return {"status": "ok", "ok": True, "restart": True,
                "message": "앱 내 재생기를 설치했습니다. 프로그램을 다시 시작해 주세요."}
    except (OSError, ValueError, KeyError, TypeError, metadata.PackageNotFoundError, subprocess.SubprocessError):
        return {"status": "error", "ok": False, "restart": False,
                "message": "현재 Qt 환경에 맞는 재생기를 설치하지 못했습니다."}
    finally:
        os.close(descriptor)
