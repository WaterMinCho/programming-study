# -*- coding: utf-8 -*-
"""파이썬 수집 진입과 작은 창·큰 글자의 조작 영역을 확인함."""
import json
import os
import platform
from pathlib import Path
from unittest import mock

from tests import guikit
from tests import test_gui as fixtures
from PyQt6.QtCore import QPoint, QT_VERSION_STR
from PyQt6.QtGui import QFontMetricsF
from PyQt6.QtWidgets import QApplication, QScrollArea
from gui import theme


class PythonDataGuiTest(fixtures.GuiTest):
    def setUp(self):
        super().setUp()
        patcher = mock.patch.dict(os.environ, {"STUDY_PYTHON_HOME": os.path.join(self.tmp, "python-home")})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_home_opens_python_consent_separately_from_ai(self):
        self.boot()
        self.win.home.show_data()
        dialog = self.win.home.data_dialog
        guikit.pump()
        self.assertEqual("python", dialog.collection.track)
        self.assertEqual("파이썬 학습 데이터", dialog.windowTitle())
        self.assertFalse(dialog.collection.status()["enabled"])
        guikit.click(dialog.toggle)
        self.assertTrue(dialog.collection.status()["enabled"])
        self.assertFalse(self.win.ai.collection.status()["enabled"] if self.win.ai else False)
        dialog.close()

    def test_small_window_largest_text_and_both_themes(self):
        self.boot()
        self.win.resize(760, 480)
        self.win.set_text("larger")
        screen = QApplication.primaryScreen()
        area = screen.availableGeometry()
        report = {"os":platform.platform(), "qt":QT_VERSION_STR, "platform":QApplication.platformName(),
                  "dpr":screen.devicePixelRatio(), "available_area":[area.x(),area.y(),area.width(),area.height()], "conditions":[]}
        for mode in ("light", "dark"):
            theme.set_mode(mode)
            home_scroll = self.win.home.findChildren(QScrollArea)[0]
            home_scroll.ensureWidgetVisible(self.win.home.data_btn)
            guikit.pump()
            button = self.win.home.data_btn
            point = button.mapTo(home_scroll.viewport(), QPoint())
            self.assertGreaterEqual(button.width(), QFontMetricsF(button.font()).horizontalAdvance(button.text()) + 24)
            self.assertGreaterEqual(point.x(), 0)
            self.assertGreaterEqual(point.y(), 0)
            self.assertLessEqual(point.x() + button.width(), home_scroll.viewport().width())
            self.assertLessEqual(point.y() + button.height(), home_scroll.viewport().height())
            self.win.home.show_data()
            dialog = self.win.home.data_dialog
            dialog.resize(640, 420)
            guikit.pump()
            self.assertLessEqual(dialog.width(), 760)
            self.assertLessEqual(dialog.height(), 480)
            condition = {"theme":mode, "text":"larger", "parent":[self.win.width(),self.win.height()],
                         "dialog":[dialog.width(),dialog.height()], "buttons":[]}
            output = os.environ.get("STUDY_UI_ARTIFACT_DIR")
            if output:
                root = Path(output)
                root.mkdir(parents=True, exist_ok=True)
                dialog.grab().save(str(root / ("python-data-top-" + mode + ".png")))
                if QApplication.platformName() == "windows":
                    screen.grabWindow(int(dialog.winId())).save(str(root / ("python-data-native-top-" + mode + ".png")))
            for button in (dialog.toggle, dialog.goal_save, dialog.export_button, dialog.delete_button, dialog.send_button, dialog.remote_delete):
                dialog.scroll.ensureWidgetVisible(button)
                guikit.pump()
                point = button.mapTo(dialog.scroll.viewport(), QPoint())
                self.assertGreaterEqual(button.width(), QFontMetricsF(button.font()).horizontalAdvance(button.text()) + 24)
                self.assertGreaterEqual(point.x(), 0)
                self.assertGreaterEqual(point.y(), 0)
                self.assertLessEqual(point.x() + button.width(), dialog.scroll.viewport().width())
                self.assertLessEqual(point.y() + button.height(), dialog.scroll.viewport().height())
                condition["buttons"].append({"text":button.text(),"x":point.x(),"y":point.y(),"width":button.width(),"height":button.height()})
            if output:
                root = Path(output)
                root.mkdir(parents=True, exist_ok=True)
                self.win.grab().save(str(root / ("python-home-" + mode + ".png")))
                dialog.grab().save(str(root / ("python-data-" + mode + ".png")))
                if QApplication.platformName() == "windows":
                    screen.grabWindow(int(dialog.winId())).save(str(root / ("python-data-native-" + mode + ".png")))
            report["conditions"].append(condition)
            dialog.close()
        if os.environ.get("STUDY_UI_ARTIFACT_DIR"):
            (Path(os.environ["STUDY_UI_ARTIFACT_DIR"]) / "report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
