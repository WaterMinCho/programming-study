# -*- coding: utf-8 -*-
"""API 제출 연결의 공개 안내·오류·작은 창 배치를 임시 기록으로 확인함."""
from pathlib import Path
from unittest import mock

from aiprep.collection import CollectionError
from gui import theme
from submission_api import Client
from tests import guikit
from PyQt6.QtCore import QPoint
from tests.test_gui_hub import HubTest


class ApiSetupTest(HubTest):
    def open_setup(self):
        win = self.boot()
        repo = Path(self.tmp) / "api-repo"
        folder = repo / "submissions/tester/r01"
        folder.mkdir(parents=True)
        (folder / "quiz.py").write_text("ANSWERS = {}\n", encoding="utf-8")
        self.git.api = Client(str(repo), "tester", {"python": win.session.collection, "ai": win.ai.collection})
        win.show_submission_setup()
        guikit.pump()
        self.capture_widget = win.submission_dialog
        return win, win.submission_dialog

    def test_setup_fits_small_window_max_text_and_both_themes(self):
        win, dialog = self.open_setup()
        win.resize(760, 480)
        win.set_text("larger")
        for selected in ("light", "dark"):
            theme.apply(guikit.APP, selected)
            area = win.screen().availableGeometry()
            dialog.resize(min(640, area.width() - 32), min(480, area.height() - 72))
            guikit.pump()
            self.assertLessEqual(dialog.width(), 760)
            self.assertLessEqual(dialog.height(), 480)
            self.assertIn("r01/quiz.py", dialog.files.toPlainText())
            self.assertGreaterEqual(dialog.connect_button.width(), dialog.connect_button.sizeHint().width())
            position = dialog.connect_button.mapTo(dialog, QPoint(0, 0))
            self.assertGreaterEqual(position.y(), 0)
            self.assertLessEqual(position.y() + dialog.connect_button.height(), dialog.height())
            self.assertEqual(dialog.invite.echoMode(), dialog.invite.EchoMode.Password)

    def test_connection_error_keeps_answers_and_shows_message(self):
        win, dialog = self.open_setup()
        dialog.url.setText("https://example.test")
        dialog.invite.setText("private-invite")
        with mock.patch.object(self.git.api, "connect", side_effect=CollectionError("초대 코드가 만료됐습니다.")):
            guikit.click(dialog.connect_button)
            self.idle()
        self.assertTrue(win.dialog.isVisible())
        self.assertIn("초대 코드가 만료", win.dialog.text.text())
        self.assertEqual(dialog.invite.text(), "")
        self.assertTrue((Path(self.tmp) / "api-repo/submissions/tester/r01/quiz.py").exists())
