import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import platform
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QPoint
from gui import theme
from gui.ai_data import LearningDataDialog
from tests import guikit
from tests.test_gui_ai import AiTest


def main():
    out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
    helper = AiTest(); helper.setUp()
    report = {"os": platform.platform(), "platform": os.environ.get("QT_QPA_PLATFORM"),
              "scale": os.environ.get("QT_SCALE_FACTOR"), "captures": [], "errors": []}
    user = ctypes.windll.user32
    user.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    try:
        win = helper.boot((760, 480)); win.go_ai(); win.set_text("larger")
        for mode in ("light", "dark"):
            theme.set_mode(mode)
            dialog = LearningDataDialog(win, win.ai.collection); dialog.show(); guikit.pump()
            for name, widget in (("top", dialog.status_text), ("consent", dialog.toggle),
                                 ("export", dialog.export_button), ("delete", dialog.delete_button),
                                 ("send", dialog.send_button), ("remote-delete", dialog.remote_delete)):
                dialog.scroll.ensureWidgetVisible(widget); guikit.pump()
                client = wintypes.RECT(); hwnd = wintypes.HWND(int(dialog.winId()))
                if not user.GetClientRect(hwnd, ctypes.byref(client)):
                    raise RuntimeError("GetClientRect failed")
                image = dialog.screen().grabWindow(int(dialog.winId()))
                path = out / (mode + "-" + name + ".png"); image.save(str(path))
                point = widget.mapTo(dialog.scroll.viewport(), QPoint())
                report["captures"].append({"file": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                                            "window": [dialog.width(), dialog.height()], "native": [image.width(), image.height()],
                                            "client": [client.right, client.bottom], "dpr": image.devicePixelRatio(),
                                            "widget": [point.x(), point.y(), widget.width(), widget.height()],
                                            "viewport": [dialog.scroll.viewport().width(), dialog.scroll.viewport().height()]})
                if image.isNull() or image.width() != client.right or image.height() != client.bottom:
                    raise RuntimeError("Native capture size mismatch")
                if name != "top" and (point.x() < 0 or point.y() < 0 or point.x() + widget.width() > dialog.scroll.viewport().width()
                                     or point.y() + widget.height() > dialog.scroll.viewport().height()):
                    raise RuntimeError("Unreachable button")
            dialog.close()
        report["runtime"] = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in
                             [Path("aiprep/collection.py"), Path("aiprep/sharing.py"), Path("gui/ai_data.py"), Path("learning_server/app.py")]}
    finally:
        helper.tearDown(); helper.doCleanups()
        path = out / "report.json"; path.write_text(json.dumps(report, indent=2) + "\n")
        assert json.loads(path.read_text()) == report


if __name__ == "__main__":
    main()
