"""합성 iframe의 실제 클릭으로 WebEngine 전체화면·복원·종료를 확인함."""
from __future__ import annotations

import argparse
import html
from importlib import metadata
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
from time import monotonic
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
POLL_MS = 25
STAGE_TIMEOUT = 15
INSTALL_TIMEOUT = 180

# 하단 44px 단추가 잘리는 조건을 실제 클릭 전에 확인함. 외부 자원은 사용하지 않음.
FRAME_HTML = '''<!doctype html><html lang="ko"><head><meta charset="utf-8">
<style>
html,body,#stage { margin:0; width:100%; height:100%; overflow:hidden; }
#stage { background:#17324d; color:white; font:20px sans-serif; }
p { margin:0; padding:24px; }
#fullscreen { position:fixed; right:0; bottom:0; width:44px; height:44px;
  border:0; background:#ffd166; color:#17212b; font-size:28px; cursor:pointer; }
#marker { position:fixed; left:0; bottom:0; width:44px; height:44px; background:#06d6a0; }
</style></head><body><main id="stage"><p>전체화면 검사</p>
<span id="marker"></span><button id="fullscreen" title="전체화면" aria-label="전체화면">⛶</button>
</main><script>
window.fixture = {clicks:0, activeGesture:false, error:null, frames:0, pointer:null};
for (const kind of ['pointermove','pointerdown','pointerup']) document.addEventListener(kind, event => {
  fixture.pointer = [kind,event.clientX,event.clientY,event.target.id];
});
function tick() { fixture.frames++; requestAnimationFrame(tick); }
requestAnimationFrame(tick);
document.getElementById('fullscreen').addEventListener('click', () => {
  fixture.clicks++;
  fixture.activeGesture = navigator.userActivation.isActive;
  document.getElementById('stage').requestFullscreen().catch(error => {
    fixture.error = error.name + ': ' + error.message;
  });
});
</script></body></html>'''

FIXTURE_HTML = '''<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none';
  frame-src 'self' about:; script-src 'unsafe-inline'; style-src 'unsafe-inline'">
<style>html,body,iframe { margin:0; width:100%; height:100%; border:0; overflow:hidden; }
iframe { display:block; }</style></head><body>
<iframe id="player" allow="fullscreen" allowfullscreen srcdoc="''' + html.escape(FRAME_HTML, quote=True) + '''"></iframe>
<script>
window.rokeyState = {kind:'ready'};
window.fixtureSnapshot = () => {
  const frame = document.getElementById('player');
  const child = frame.contentWindow, doc = frame.contentDocument;
  const button = doc && doc.getElementById('fullscreen');
  if (!button || !child.fixture) return null;
  const f = frame.getBoundingClientRect(), b = button.getBoundingClientRect();
  return {
    ready: document.readyState === 'complete' && doc.readyState === 'complete',
    fullscreen: document.fullscreenElement?.id || null,
    childFullscreen: doc.fullscreenElement?.id || null,
    viewport:[innerWidth,innerHeight], childViewport:[child.innerWidth,child.innerHeight],
    button:[f.x+b.x,f.y+b.y,b.width,b.height],
    scroll:[scrollX,scrollY,child.scrollX,child.scrollY],
    ...child.fixture
  };
};
</script></body></html>'''


def save_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def install_engine(out):
    """첫 설치 검사로 만든 CI 전용 환경에만 재생기를 추가함."""
    from tools import video_setup

    require(os.environ.get("CI", "").lower() in ("true", "1"),
            "설치는 CI에서만 실행합니다. 준비된 로컬 환경은 --skip-install을 사용하세요.")
    require(Path(sys.prefix).resolve() == (out.parent / "venv").resolve()
            and sys.prefix != sys.base_prefix, "첫 설치 검사에서 만든 전용 환경으로 실행해 주세요.")
    fresh = json.loads((out.parent / "report.json").read_text(encoding="utf-8"))
    require(fresh.get("success") and fresh.get("fresh_install"), "첫 설치 검사를 먼저 통과해야 합니다.")
    require(Path(fresh["python_prefix"]).resolve() == Path(sys.prefix).resolve(),
            "첫 설치 보고서와 실행 환경이 일치하지 않습니다.")
    before = video_setup.core_versions()
    result = video_setup.install()
    after = video_setup.core_versions()
    report = {"result": result, "core_before": before, "core_after": after,
              "core_preserved": before == after, "success": bool(result.get("ok") and before == after)}
    save_json(out / "install.json", report)
    require(report["success"], "재생기 설치 또는 기존 Qt 버전 보존을 확인하지 못했습니다.")


def probe(out):
    from PyQt6 import sip
    from PyQt6.QtCore import QCoreApplication, QEvent, QEventLoop, QPoint, QRect, Qt, QTimer, qVersion
    from PyQt6.QtTest import QTest
    from PyQt6.QtWidgets import QApplication
    from career.player_html import APP_ORIGIN
    from gui import motion, theme
    from gui.video_viewer import VideoDialog, create_engine

    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    app = QApplication(["check_video_fullscreen"])
    app.setQuitOnLastWindowClosed(False)
    theme.apply(app, "light")
    motion.enabled = False
    report = {"success": False, "qt": qVersion(), "qt_platform": app.platformName(),
              "scale": os.environ.get("QT_SCALE_FACTOR", "1"), "synthetic_only": True,
              "packages": {name: metadata.version(name) for name in
                           ("PyQt6", "PyQt6-Qt6", "PyQt6-sip", "PyQt6-WebEngine", "PyQt6-WebEngine-Qt6")},
              "requests": [], "events": [], "external_urls": [], "snapshots": {}, "destroyed": []}
    engines = []
    dialog = None

    def checkpoint():
        save_json(out / "probe.json", report)

    def pump():
        # 주기는 이벤트 처리 간격이며 통과 여부는 매번 실제 상태로 판단함.
        loop = QEventLoop()
        QTimer.singleShot(POLL_MS, loop.quit)
        loop.exec()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def wait(label, sample, ready):
        report["stage"] = label
        checkpoint()
        deadline = monotonic() + STAGE_TIMEOUT
        previous = None
        while monotonic() < deadline:
            value = sample()
            report["last_observation"] = value
            if ready(value):
                # 연속한 관측에서 좌표가 같아야 지연된 Qt 배치까지 끝난 것으로 처리함.
                geometry = value.get("geometry") if isinstance(value, dict) else value
                if geometry == previous:
                    checkpoint()
                    return value
                previous = geometry
            else:
                previous = None
            pump()
        checkpoint()
        raise TimeoutError(label + ": 제한 시간 안에 필요한 상태를 확인하지 못했습니다.")

    def js(script):
        values = []
        engine.page.runJavaScript(script, values.append)
        deadline = monotonic() + STAGE_TIMEOUT
        while not values and monotonic() < deadline:
            pump()
        require(bool(values), "문서 상태 조회가 제한 시간을 넘었습니다.")
        return values[0]

    def rect_in(widget, parent):
        return QRect(widget.mapTo(parent, QPoint()), widget.size())

    def paint_state():
        # DOM 준비만으로는 Chromium의 첫 화면과 iframe 입력 영역이 준비되지 않음.
        # 배경·양쪽 하단 표식이 실제로 그려진 뒤 클릭하며 고정 시간은 기다리지 않음.
        picture = engine.widget.grab().toImage()
        if picture.isNull():
            return {"ready": False, "colors": {}}
        ratio = picture.devicePixelRatio()
        width, height = engine.widget.width(), engine.widget.height()
        points = {"background": (width // 2, height // 2, "#17324d"),
                  "bottom_left": (5, height - 5, "#06d6a0"),
                  "bottom_right": (width - 5, height - 5, "#ffd166")}
        colors = {}
        for name, (x, y, expected) in points.items():
            point = QPoint(round(x * ratio), round(y * ratio))
            if not picture.rect().contains(point):
                return {"ready": False, "colors": colors}
            colors[name] = picture.pixelColor(point).name()
        return {"ready": all(colors[name] == point[2] for name, point in points.items()), "colors": colors}

    def sample():
        require(dialog.engine is engine and not engine.closed, "재생 엔진이 중간에 교체되거나 닫혔습니다.")
        require(not report["external_urls"], "외부 브라우저 열기가 요청되었습니다.")
        dom = js("window.fixtureSnapshot?.() || null")
        viewport = dialog.shell.scroll.viewport()
        view_rect = rect_in(engine.widget, viewport)
        client_rect = rect_in(engine.widget, dialog)
        proxy = engine.widget.focusProxy()
        return {"geometry": list(dialog.geometry().getRect()),
                "normal_geometry": list(dialog.normalGeometry().getRect()),
                "frame_geometry": list(dialog.frameGeometry().getRect()),
                "view_in_viewport": list(view_rect.getRect()), "viewport": list(viewport.rect().getRect()),
                "view_in_window": list(client_rect.getRect()), "window": list(dialog.rect().getRect()),
                "view_fully_visible": viewport.rect().contains(view_rect),
                "view_fills_window": client_rect == dialog.rect() and view_rect == viewport.rect(),
                "scroll_maximum": [dialog.shell.scroll.horizontalScrollBar().maximum(),
                                   dialog.shell.scroll.verticalScrollBar().maximum()],
                "window_fullscreen": dialog.isFullScreen(), "dialog_fullscreen": dialog._fullscreen,
                "same_engine": dialog.engine is engine, "player_state": dialog.state,
                "page_visible": engine.page.isVisible(), "view_visible": engine.widget.isVisible(),
                "focus_proxy_ready": proxy is not None and proxy.isVisible(),
                "dom": dom, "paint": paint_state()}

    def dom_ready(value):
        dom = value["dom"]
        return (dom and dom["ready"] and dom["frames"] >= 2 and value["focus_proxy_ready"]
                and value["paint"]["ready"]
                and value["player_state"] == "ready"
                and dom["viewport"] == [engine.widget.width(), engine.widget.height()]
                and dom["childViewport"] == dom["viewport"])

    def normal_ready(value):
        return (dom_ready(value) and not value["window_fullscreen"] and not value["dialog_fullscreen"]
                and not value["dom"]["fullscreen"] and not value["dom"]["childFullscreen"]
                and value["view_fully_visible"])

    def fullscreen_ready(value):
        return (dom_ready(value) and value["window_fullscreen"] and value["dialog_fullscreen"]
                and value["dom"]["fullscreen"] == "player" and value["dom"]["childFullscreen"] == "stage"
                and value["view_fills_window"] and value["scroll_maximum"] == [0, 0]
                and dialog.geometry() == dialog.screen().geometry())

    def capture(name, value):
        dialog.repaint()
        shot = dialog.grab()
        require(not shot.isNull() and shot.save(str(out / (name + ".png"))), "창 그림을 저장하지 못했습니다.")
        value["device_pixel_ratio"] = dialog.devicePixelRatioF()
        value["image_pixels"] = [shot.width(), shot.height()]
        value["screen"] = list(dialog.screen().geometry().getRect())
        value["work_area"] = list(dialog.screen().availableGeometry().getRect())
        if app.platformName() == "windows":
            # 창 ID의 이전 버퍼 대신 현재 바탕 화면에서 클라이언트 영역을 가져옴.
            screen = dialog.screen()
            desktop = screen.grabWindow(0)
            ratio = desktop.devicePixelRatioF()
            origin = dialog.mapToGlobal(QPoint()) - screen.geometry().topLeft()
            native = desktop.copy(round(origin.x() * ratio), round(origin.y() * ratio),
                                  round(dialog.width() * ratio), round(dialog.height() * ratio))
            require(not native.isNull() and native.save(str(out / (name + "-native.png"))),
                    "운영체제 화면을 저장하지 못했습니다.")
            value["native_image_pixels"] = [native.width(), native.height()]
        report["snapshots"][name] = value
        checkpoint()

    def click_fullscreen():
        value = sample()
        dom = value["dom"]
        require(dom_ready(value) and value["view_fully_visible"], "하단 단추를 포함한 재생 영역이 잘렸습니다.")
        x, y, width, height = dom["button"]
        require([width, height] == [44, 44] and x + width == dom["viewport"][0]
                and y + height == dom["viewport"][1], "44px 전체화면 단추가 오른쪽 아래에 없습니다.")
        button_rect = QRect(round(x), round(y), round(width), round(height))
        require(engine.widget.rect().contains(button_rect), "전체화면 단추가 재생 영역 밖으로 잘렸습니다.")
        viewport = dialog.shell.scroll.viewport()
        require(viewport.rect().contains(button_rect.translated(engine.widget.mapTo(viewport, QPoint()))),
                "전체화면 단추가 스크롤 뷰포트에 가려졌습니다.")
        proxy = engine.widget.focusProxy()
        dialog.activateWindow()
        proxy.setFocus()
        point = proxy.mapFrom(engine.widget, button_rect.center())
        report.setdefault("clicks", []).append({"button": dom["button"], "proxy_point": [point.x(), point.y()],
                                                "proxy_rect": list(proxy.rect().getRect()),
                                                "proxy_has_focus": proxy.hasFocus()})
        checkpoint()
        # 복원 후 커서가 같은 자리에 있어도 누를 수 있음. 이동 이벤트는 통과 조건이 아님.
        QTest.mouseMove(proxy, point)
        pump()
        if app.platformName() == "windows":
            hit = QApplication.widgetAt(proxy.mapToGlobal(point))
            require(hit is not None and (hit is engine.widget or engine.widget.isAncestorOf(hit)),
                    "전체화면 단추 위에 다른 위젯이 있습니다.")
        QTest.mousePress(proxy, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point)
        try:
            wait("button_press", lambda: js("window.fixtureSnapshot()"),
                 lambda state: state["pointer"] is not None and state["pointer"][0] == "pointerdown"
                 and state["pointer"][3] == "fullscreen")
        finally:
            QTest.mouseRelease(proxy, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point)

    def factory(parent, on_event, open_url):
        def event(kind, code=None):
            report["events"].append({"kind": kind, "code": code})
            on_event(kind, code)

        result = create_engine(parent, event, open_url)
        engines.append(result)
        result.page.fullScreenRequested.connect(lambda request: report["requests"].append({
            "toggle_on": request.toggleOn(), "origin": request.origin().toString(),
            "origin_empty": request.origin().isEmpty(), "page_url": result.page.url().toString()}))
        for name, obj in (("engine", result), ("view", result.widget), ("page", result.page), ("profile", result.profile)):
            obj.destroyed.connect(lambda _=None, name=name: report["destroyed"].append(name))
        return result

    try:
        require(sys.platform != "win32" or app.platformName() == "windows", "Windows에서는 native 플랫폼으로 검사해 주세요.")
        video = SimpleNamespace(video_id="___________", title="합성 전체화면 검사", author="로컬 검사 자료", embeddable=True)
        dialog = VideoDialog(None, video, lambda url: report["external_urls"].append(url) or False, engine_factory=factory)
        with mock.patch("gui.video_viewer.player_html", return_value=FIXTURE_HTML):
            dialog.open()
        require(len(engines) == 1 and dialog.engine is engines[0], "실제 재생 엔진을 만들지 못했습니다.")
        engine = engines[0]
        normal = wait("normal", sample, normal_ready)
        require(engine.page.url().toString() == APP_ORIGIN + "/", "실제 wrapper의 기준 주소와 다릅니다.")
        normal_geometry = normal["geometry"]
        capture("normal", normal)
        click_fullscreen()
        full = wait("fullscreen", sample, fullscreen_ready)
        require(full["dom"]["clicks"] == 1 and full["dom"]["activeGesture"] and not full["dom"]["error"],
                "실제 사용자 클릭으로 전체화면에 진입하지 못했습니다.")
        require(any(row["toggle_on"] for row in report["requests"]), "WebEngine 전체화면 요청이 없습니다.")
        capture("fullscreen", full)
        # WebEngine에 초점이 있는 실제 Escape 경로로 창과 DOM을 함께 복원함.
        focused = QApplication.focusWidget()
        require(focused is engine.widget.focusProxy(), "재생기에 키보드 초점이 없습니다.")
        QTest.keyClick(focused, Qt.Key.Key_Escape)
        restored = wait("restored", sample,
                        lambda value: normal_ready(value) and value["geometry"] == normal_geometry)
        require(any(not row["toggle_on"] for row in report["requests"]), "전체화면 해제 요청이 없습니다.")
        capture("restored", restored)
        click_fullscreen()
        again = wait("reentered", sample, fullscreen_ready)
        require(again["dom"]["clicks"] == 2 and len(engines) == 1, "재진입 중 문서 또는 엔진이 교체되었습니다.")
        require(again["dom"]["activeGesture"] and not again["dom"]["error"]
                and sum(row["toggle_on"] for row in report["requests"]) == 2,
                "두 번째 클릭의 전체화면 요청을 확인하지 못했습니다.")
        report["snapshots"]["reentered"] = again
        dialog.close()
        require(dialog.closed and not dialog.isVisible() and dialog.engine is None and engine.closed,
                "전체화면에서 닫은 뒤 창 또는 엔진이 남았습니다.")
        require(not engine.poll_timer.isActive() and not engine.deadline.isActive(), "닫은 엔진의 타이머가 실행 중입니다.")
        wait("cleanup", lambda: sorted(report["destroyed"]),
             lambda value: value == ["engine", "page", "profile", "view"])
        require(sip.isdeleted(engine), "재생 엔진의 지연 삭제가 끝나지 않았습니다.")
        report["engine_instances"] = len(engines)
        report["empty_origin_observed"] = any(row["toggle_on"] and row["origin_empty"] for row in report["requests"])
        report["success"] = True
    except Exception as error:
        report["error"] = {"type": type(error).__name__, "message": str(error)}
    finally:
        if dialog is not None:
            dialog.close()
        checkpoint()
    return 0 if report["success"] else 1


def run_child(args, phase, timeout):
    """Qt나 설치가 응답하지 않아도 소유한 자식 프로세스만 제한 시간 뒤 정리함."""
    command = [sys.executable, str(Path(__file__).resolve()), "--out", str(args.out), "--worker", phase]
    with (args.out / (phase + ".log")).open("w", encoding="utf-8") as log:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                   start_new_session=sys.platform != "win32")
        try:
            return process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            if sys.platform == "win32":
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                               stdout=log, stderr=log, timeout=10, check=False)
            else:
                os.killpg(process.pid, signal.SIGKILL)
            process.kill()
            process.wait(timeout=10)
            return 124


def main():
    parser = argparse.ArgumentParser(description="외부 영상 없이 실제 전체화면 클릭과 복원을 확인합니다.")
    parser.add_argument("--out", required=True, type=Path, help="결과를 저장할 새 폴더")
    parser.add_argument("--skip-install", action="store_true", help="이미 설치된 재생기를 사용합니다.")
    parser.add_argument("--timeout", type=float, default=90, help="화면 검사 프로세스의 제한 시간(초)")
    parser.add_argument("--worker", choices=("install", "probe"), help=argparse.SUPPRESS)
    args = parser.parse_args()
    require(args.timeout > 0, "제한 시간은 0보다 커야 합니다.")
    args.out = args.out.resolve()
    args.out.mkdir(parents=True, exist_ok=True)
    os.chdir(ROOT)
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu")
    os.environ["STUDY_AUTO_SYNC"] = "0"
    os.environ["STUDY_NODE_PROBE"] = "0"
    if args.worker == "probe":
        return probe(args.out)
    if args.worker == "install":
        install_engine(args.out)
        return 0
    if (args.out / "report.json").exists():
        parser.error("이전 보고서가 없는 새 폴더를 지정해 주세요.")
    (args.out / "fixture.html").write_text(FIXTURE_HTML, encoding="utf-8")
    report = {"success": False, "skip_install": args.skip_install, "timeout_seconds": args.timeout,
              "synthetic_only": True, "phases": {}}
    try:
        for phase, timeout in (("install", INSTALL_TIMEOUT), ("probe", args.timeout)):
            if phase == "install" and args.skip_install:
                continue
            report["phases"][phase] = run_child(args, phase, timeout)
            if report["phases"][phase] != 0:
                break
        report["success"] = (report["phases"].get("probe") == 0
                             and json.loads((args.out / "probe.json").read_text(encoding="utf-8")).get("success") is True)
    except Exception as error:
        report["error"] = {"type": type(error).__name__, "message": str(error)}
    save_json(args.out / "report.json", report)
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
