"""논문 목록의 로컬 도식·원문 연결·대체 설명과 읽던 위치를 확인함."""
from dataclasses import replace
import json
import os
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from tests import guikit
from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtTest import QSignalSpy, QTest
from PyQt6.QtWidgets import QLabel, QPushButton

from career.catalog import Catalog, load_catalog
from gui import theme
from gui.career_magazine import CareerMagazinePage, SourceDetails
from gui.career_paper_preview import PREVIEW_STAGES
from gui.paper_explainer import PaperDiagram, PaperExplanationDialog, load_explanations


class PaperPreviewTest(unittest.TestCase):
    def setUp(self):
        self.catalog = load_catalog()
        self.explanations = load_explanations()
        self.windows = []
        self.original_theme = dict(theme.state)

    def tearDown(self):
        for window in reversed(self.windows):
            window.close()
            window.deleteLater()
        guikit.pump()
        theme.set_text(self.original_theme["text"])
        theme.set_mode(self.original_theme["mode"])

    def settle(self, page):
        previous, stable = None, 0
        for _ in range(100):
            guikit.pump(3)
            signature = (page.content.size(), page.scroll.verticalScrollBar().maximum(),
                         tuple((preview.size(), preview.pos()) for preview in page.paper_previews.values()),
                         tuple((child.size(), child.mapTo(page.scroll.viewport(), QPoint()))
                               for child in page.paper_content.findChildren(QLabel) if child.isVisibleTo(page.content)))
            stable = stable + 1 if signature == previous else 0
            anchor_ready = (page._anchor is None or
                            abs(page._anchor[0].mapTo(page.scroll.viewport(), QPoint()).y() - page._anchor[1]) <= 1)
            if stable >= 3 and not page._settling and not page._timer.isActive() and anchor_ready:
                return
            previous = signature
        self.fail("논문 목록 배치가 안정되지 않았음")

    def show(self, **kwargs):
        page = CareerMagazinePage(catalog=kwargs.pop("catalog", self.catalog), **kwargs)
        self.windows.append(page)
        page.resize(760, 480)
        page.show()
        page.tabs.picked.emit(1)
        self.settle(page)
        return page

    def details(self, preview, title):
        return next(row for row in preview.parentWidget().findChildren(SourceDetails) if row.title == title)

    def labels(self, widget):
        return [label.text() for label in widget.findChildren(QLabel)]

    def test_browse_reuses_representative_stage_and_keeps_conditions_and_boundary_visible(self):
        figure, paper_open, source, play, stop = (Mock() for _ in range(5))
        with patch("socket.socket", side_effect=AssertionError("외부 통신")), \
                patch("subprocess.Popen", side_effect=AssertionError("외부 실행")):
            page = self.show(on_figure=figure, on_paper=paper_open, on_source=source,
                             on_video=play, on_stop=stop)
            expected = {"paper-mobilenetv4": 1, "paper-convnext-v2": 0, "paper-dinov2": 0,
                        "paper-sam2": 0, "paper-dora-weight-decomposed": 0}
            self.assertEqual(PREVIEW_STAGES, expected)
            for paper in self.catalog.papers:
                preview = page.paper_previews[paper.paper_id]
                explanation = self.explanations[paper.paper_id]
                stage = expected[paper.paper_id]
                step = explanation["steps"][stage]
                self.assertIsInstance(preview.diagram, PaperDiagram)
                self.assertEqual(preview.stage, stage)
                self.assertEqual(preview.diagram.stage, stage)
                self.assertIn(step["text"], preview.accessibleDescription())
                visible = [label.text() for label in preview.parentWidget().findChildren(QLabel)
                           if label.isVisibleTo(page.content)]
                for text in (explanation["short_title"], step["question"], step["shape"], step["text"],
                             f"대표 단계 {stage + 1} · " + step["title"], explanation["axes"], explanation["boundary"]):
                    self.assertIn(text, visible)
                for title in ("논문 설명·선행 개념", "출처·검토 범위"):
                    self.assertTrue(self.details(preview, title).content.isHidden())
            for callback in (figure, paper_open, source, play, stop):
                callback.assert_not_called()

    def test_picture_keyboard_and_button_request_the_same_paper_once(self):
        figure = Mock()
        page = self.show(on_figure=figure)
        signals = QSignalSpy(page.figure_requested)
        for paper in self.catalog.papers:
            preview = page.paper_previews[paper.paper_id]
            section = preview.parentWidget()
            button = next(row for row in section.findChildren(QPushButton) if row.text() == "그림 설명 보기")
            for target, key in ((preview, None), (preview, Qt.Key.Key_Return), (preview, Qt.Key.Key_Enter),
                                (preview, Qt.Key.Key_Space), (button, None)):
                with self.subTest(paper=paper.paper_id, key=key, target=type(target).__name__):
                    page.scroll.ensureWidgetVisible(target)
                    self.settle(page)
                    before = len(signals)
                    if key is None:
                        guikit.click(target)
                    else:
                        target.setFocus()
                        QTest.keyClick(target, key)
                    figure.assert_called_once_with(paper)
                    self.assertEqual(len(signals), before + 1)
                    self.assertIs(signals[-1][0], paper)
                    figure.reset_mock()

    def test_existing_description_prerequisites_sources_and_license_remain_in_toggles(self):
        paper_open, source = Mock(), Mock()
        page = self.show(on_paper=paper_open, on_source=source)
        for paper in self.catalog.papers:
            preview = page.paper_previews[paper.paper_id]
            description = self.details(preview, "논문 설명·선행 개념")
            guikit.click(description.button)
            self.settle(page)
            texts = self.labels(description.content)
            self.assertIn(paper.summary, texts)
            self.assertIn(paper.beginner_explanation, texts)
            self.assertIn("읽기에 필요한 개념 · " + ", ".join(paper.prerequisites), texts)
            details = self.details(preview, "출처·검토 범위")
            guikit.click(details.button)
            self.settle(page)
            texts = "\n".join(self.labels(details.content))
            for text in ("출처 · " + paper.title, paper.verification_scope, paper.license_label,
                         paper.license_scope, paper.examined_version, paper.checked_date):
                self.assertIn(text, texts)
            links = {row.text(): row for row in details.content.findChildren(QPushButton)}
            self.assertEqual(links["논문 원문 열기"].toolTip(), paper.url)
            guikit.click(links["논문 원문 열기"])
            paper_open.assert_called_once_with(paper)
            paper_open.reset_mock()
            self.assertEqual(links["이용 조건 원문"].toolTip(), paper.license_url)
            guikit.click(links["이용 조건 원문"])
            source.assert_called_once_with(paper.license_url)
            source.reset_mock()

    def test_unknown_and_unreadable_explanations_show_existing_input_operation_output(self):
        known = self.catalog.papers[0]
        unknown = replace(known, paper_id="unknown-paper")
        for papers, failure in (((unknown,), None), ((known,), FileNotFoundError()), ((known,), ValueError())):
            with self.subTest(failure=type(failure).__name__):
                catalog = replace(self.catalog, papers=papers)
                figure = Mock()
                with patch("gui.career_magazine.load_explanations", side_effect=failure,
                           return_value=self.explanations), \
                        patch("socket.socket", side_effect=AssertionError("외부 통신")):
                    page = self.show(catalog=catalog, on_figure=figure)
                    preview = next(iter(page.paper_previews.values()))
                    self.assertIsNone(preview.diagram)
                    for sentence in known.figure_description:
                        self.assertIn(sentence, preview.accessibleDescription())
                    self.assertIn("대표 그림을 표시할 수 없습니다.", self.labels(preview))
                    guikit.click(preview)
                    figure.assert_called_once_with(papers[0])
        bare = replace(unknown, figure_description=())
        page = self.show(catalog=replace(self.catalog, papers=(bare,)), on_figure=Mock())
        preview = page.paper_previews[bare.paper_id]
        self.assertEqual(preview.accessibleDescription(), bare.beginner_explanation)
        self.assertFalse(preview.isEnabled())
        theme.set_text("larger")
        self.settle(page)
        self.assertGreaterEqual(preview.height(), preview.heightForWidth(preview.width()))
        for label in preview.findChildren(QLabel):
            self.assertGreaterEqual(label.height(), label.heightForWidth(label.width()))

    def test_paper_data_absence_retains_distinct_messages_without_loading_diagrams(self):
        for state, message in (("empty", "공개한 논문 해설이 없습니다."),
                               ("unavailable", "논문 해설 자료는 아직 제공하지 않습니다."),
                               ("invalid", "논문 해설 자료를 읽지 못했습니다.")):
            with self.subTest(state=state), patch("gui.career_magazine.load_explanations") as load:
                page = self.show(catalog=Catalog(states={"roles": state, "videos": state, "papers": state}))
                self.assertFalse(page.paper_previews)
                self.assertIn(message, "\n".join(self.labels(page.paper_content)))
                load.assert_not_called()

    def test_diagrams_fit_both_themes_maximum_font_and_small_and_wide_windows(self):
        page = self.show(on_figure=Mock(), on_paper=Mock(), on_source=Mock())
        self.capture_widget = page
        requested = ((760, 480), (1280, 800))
        native = os.name == "nt" and guikit.APP.platformName() == "windows"
        room = page.screen().availableGeometry()
        sizes = (requested[0], (min(1280, room.width() - 32), min(800, room.height() - 64))) if native else requested
        measurements = []
        for mode in ("light", "dark"):
            theme.set_mode(mode)
            for text in ("normal", "larger"):
                theme.set_text(text)
                for wanted, (width, height) in zip(requested, sizes):
                    with self.subTest(mode=mode, text=text, width=width):
                        page.resize(width, height)
                        if native:
                            page.move(room.topLeft() + QPoint(16, 32))
                        self.settle(page)
                        self.assertEqual(page.width(), width)
                        self.assertEqual(page.height(), height)
                        measurements.append({"requested": list(wanted), "actual": [page.width(), page.height()],
                                             "available": list(room.getRect()), "platform": guikit.APP.platformName(),
                                             "mode": mode, "text": text, "scale": page.devicePixelRatioF()})
                        if native:
                            self.assertTrue(room.contains(page.frameGeometry()), "창 전체를 표시할 작업 영역이 필요함")
                        self.assertLessEqual(page.content.width(), page.scroll.viewport().width())
                        for paper_id, preview in page.paper_previews.items():
                            self.assertGreaterEqual(preview.height(), preview.heightForWidth(preview.width()))
                            diagram = preview.diagram
                            scene = diagram.scene()
                            self.assertGreaterEqual(diagram.height(), diagram.heightForWidth(diagram.width()))
                            self.assertTrue(scene.ink_groups)
                            for ink in scene.ink_groups:
                                self.assertGreaterEqual(ink.left(), 0, paper_id)
                                self.assertLessEqual(ink.right(), diagram.width(), paper_id)
                                self.assertGreaterEqual(ink.top(), 0, paper_id)
                                self.assertLessEqual(ink.bottom(), diagram.height(), paper_id)
                            layouts = [op[1] for op in scene.operations if op[0] == "text"]
                            self.assertEqual(layouts[0].font().pixelSize(), theme.TYPE["body"][0])
                            for button in preview.parentWidget().findChildren(QPushButton):
                                if button.isVisibleTo(page.content):
                                    self.assertGreaterEqual(button.width(), button.sizeHint().width())
                        destination = os.environ.get("CAREER_EVIDENCE")
                        if destination and text == "larger" and width == 760:
                            folder = Path(destination)
                            folder.mkdir(parents=True, exist_ok=True)
                            for paper_id, preview in page.paper_previews.items():
                                page.scroll.ensureWidgetVisible(preview)
                                self.settle(page)
                                if not native or room.contains(page.frameGeometry()):
                                    page.repaint()
                                    guikit.pump()
                                    self.assertTrue(page.grab().save(str(folder / f"{paper_id}-{mode}.png")))
        if os.environ.get("CAREER_EVIDENCE"):
            folder = Path(os.environ["CAREER_EVIDENCE"])
            folder.mkdir(parents=True, exist_ok=True)
            (folder / "paper-preview-window-sizes.json").write_text(json.dumps(measurements, ensure_ascii=False, indent=2),
                                                                  encoding="utf-8")

    def test_toggles_tabs_font_and_detail_dialog_preserve_reading_position(self):
        dialogs = []
        page = None

        def open_figure(paper):
            dialog = PaperExplanationDialog(paper, page)
            self.windows.append(dialog)
            dialogs.append(dialog)
            dialog.open()

        page = self.show(on_figure=open_figure)
        preview = list(page.paper_previews.values())[2]
        details = self.details(preview, "논문 설명·선행 개념")
        page.scroll.ensureWidgetVisible(details.button)
        details.button.setFocus()
        self.settle(page)
        before = details.button.mapTo(page.scroll.viewport(), QPoint()).y()
        for opened in (True, False, True):
            guikit.click(details.button)
            self.settle(page)
            self.assertEqual(details.content.isVisible(), opened)
            self.assertAlmostEqual(details.button.mapTo(page.scroll.viewport(), QPoint()).y(), before, delta=1)
        page.tabs.picked.emit(0)
        self.settle(page)
        page.tabs.picked.emit(1)
        self.settle(page)
        self.assertTrue(details.button.isChecked())
        self.assertAlmostEqual(details.button.mapTo(page.scroll.viewport(), QPoint()).y(), before, delta=1)
        anchor, offset = page._anchor
        theme.set_text("larger")
        self.settle(page)
        self.assertAlmostEqual(anchor.mapTo(page.scroll.viewport(), QPoint()).y(), offset, delta=1)
        for width in (1280, 760):
            page.resize(width, 480)
            self.settle(page)
            self.assertAlmostEqual(anchor.mapTo(page.scroll.viewport(), QPoint()).y(), offset, delta=1)
        page.scroll.ensureWidgetVisible(preview)
        preview.setFocus()
        self.settle(page)
        position = page.scroll.verticalScrollBar().value()
        QTest.keyClick(preview, Qt.Key.Key_Return)
        dialog = dialogs[-1]
        guikit.wait_until(lambda: not dialog._restoring)
        self.assertIs(dialog.paper, preview.paper)
        self.assertEqual(dialog.stage, 0)
        QTest.keyClick(dialog, Qt.Key.Key_Escape)
        self.settle(page)
        self.assertEqual(page.scroll.verticalScrollBar().value(), position)
        self.assertIs(page.focusWidget(), preview)
