"""작은 수치와 도식의 축·단계·읽던 위치를 임시 창에서 확인함."""
from dataclasses import replace
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tests import guikit
from PyQt6 import sip
from PyQt6.QtCore import QLineF, QPoint
from PyQt6.QtGui import QFontMetricsF
from PyQt6.QtTest import QSignalSpy
from PyQt6.QtWidgets import QPushButton, QWidget

from career import load_catalog
from gui import kit, motion, theme
from gui.paper_explainer import EXPLANATIONS, MASK, PAPER_IDS, PaperExplanationDialog, load_explanations, small_examples


class PaperExplainerTest(unittest.TestCase):
    def setUp(self):
        self.original_theme = dict(theme.state)
        self.papers = load_catalog().papers
        self.windows = []

    def tearDown(self):
        for window in self.windows:
            window.close()
            window.deleteLater()
        guikit.pump()
        theme.set_text(self.original_theme["text"])
        theme.set_mode(self.original_theme["mode"])

    def settle(self, window):
        previous, stable = None, 0
        for _ in range(80):
            guikit.pump(3)
            current = (window.panel.body.size(), window.diagram.size(), window.panel.scroll.verticalScrollBar().maximum(),
                       window.panel.footer.size(), window.panel.header.size())
            stable = stable + 1 if current == previous else 0
            if stable >= 3 and not window._restoring:
                self.assertTrue(window.layout_stable)
                return
            previous = current
        self.fail("논문 화면의 배치가 안정되지 않았음")

    def show(self, paper=None):
        window = PaperExplanationDialog(paper or self.papers[0])
        self.windows.append(window)
        window.resize(760, 480)
        window.show()
        self.settle(window)
        self.capture_widget = window
        return window

    def test_five_papers_have_four_stages_and_no_external_image_dependencies(self):
        data = load_explanations()
        self.assertEqual(set(data), set(PAPER_IDS))
        self.assertEqual(sum(len(row["steps"]) for row in data.values()), 20)
        text = EXPLANATIONS.read_text()
        for forbidden in ("/Users/", "<img", "data:image", ".png", ".jpg", "transcript"):
            self.assertNotIn(forbidden, text)
        with patch("socket.socket", side_effect=AssertionError("외부 통신")):
            for paper in self.papers:
                dialog = self.show(paper)
                self.assertFalse(dialog.answer.isVisible())
                self.assertEqual(dialog.stage, 0)

    def test_small_examples_recalculate_convolution_and_pointwise(self):
        mobile = small_examples()["mobile"]
        self.assertEqual(mobile["depthwise"][0][1][1], 1+2+3+5+6+7+9+10+11)
        self.assertEqual(mobile["depthwise"][0][0][0], 1+2+5+6)
        self.assertEqual([plane[1][1] for plane in mobile["output"]], [54, 108, 162, 54])
        self.assertEqual((len(mobile["output"]), len(mobile["output"][0]), len(mobile["output"][0][0])), (4,4,4))

    def test_small_examples_recalculate_grn_and_dora_columns(self):
        examples = small_examples()
        self.assertEqual(examples["grn"]["norms"], [5,10])
        self.assertEqual(examples["grn"]["mean"], 7.5)
        self.assertAlmostEqual(examples["grn"]["relative"][0], 2/3)
        self.assertLess(examples["grn"]["actual_relative"][0], 2/3)
        self.assertEqual(examples["dora"]["norms"], [5,1])
        self.assertEqual(examples["dora"]["output"], [[3,0],[4,2]])
        for col in range(2):
            self.assertAlmostEqual(math.hypot(*(row[col] for row in examples["dora"]["unit"])), 1)

    def test_patch_and_mask_shapes_and_zero_based_coordinates(self):
        examples = small_examples()
        self.assertEqual(examples["dino"], {"patches":4,"patch_values":588,"tokens":5,"width":4})
        self.assertEqual((42//14)*(28//14)+1, 7)
        self.assertEqual(examples["sam"]["shape"], (4,5))
        self.assertEqual(examples["sam"]["point_value"], 1)
        self.assertEqual(sum(map(sum,MASK)), 6)
        self.assertEqual(len({len(row) for row in MASK}), 1)

    def test_step_roundtrip_keeps_scroll_and_answer_state_per_step(self):
        dialog = self.show()
        bar = dialog.panel.scroll.verticalScrollBar()
        bar.setValue(min(420,bar.maximum()))
        self.settle(dialog)
        dialog._remember()
        before = bar.value()
        guikit.click(dialog.answer_button)
        self.settle(dialog)
        before = bar.value()
        self.assertTrue(dialog.answer.isVisible())
        dialog.set_stage(1)
        self.settle(dialog)
        self.assertFalse(dialog.answer.isVisible())
        self.assertEqual(bar.value(),0)
        dialog.set_stage(0)
        self.settle(dialog)
        self.assertTrue(dialog.answer.isVisible())
        self.assertEqual(bar.value(),before)
        guikit.click(dialog.answer_button)
        self.settle(dialog)
        self.assertFalse(dialog.answer.isVisible())
        self.assertFalse(dialog.set_stage(-1))
        self.assertFalse(dialog.set_stage(4))

    def test_font_theme_and_width_changes_preserve_current_stage_and_text_anchor(self):
        dialog = self.show(self.papers[2])
        dialog.set_stage(2)
        self.settle(dialog)
        dialog.panel.scroll.ensureWidgetVisible(dialog.question)
        self.settle(dialog)
        dialog._remember()
        state = replace(dialog._states[2])
        theme.set_text("larger")
        kit.refont(dialog)
        theme.set_mode("dark")
        self.settle(dialog)
        self.assertEqual(dialog.stage,2)
        target = dialog.anchors[state.key]
        top = target.mapTo(dialog.panel.scroll.viewport(),QPoint()).y()
        wanted = -state.fraction*dialog.diagram.height() if state.relative else state.offset
        self.assertLessEqual(abs(top-wanted),1)
        dialog.resize(1024,700)
        self.settle(dialog)
        self.assertEqual(dialog.stage,2)
        self.assertTrue(dialog.layout_stable)

    def test_visible_diagram_top_keeps_pixel_gap_when_font_changes(self):
        theme.set_text("normal")
        dialog=self.show()
        bar=dialog.panel.scroll.verticalScrollBar()
        bar.setValue(dialog.diagram.mapTo(dialog.panel.body,QPoint()).y()-20)
        self.settle(dialog)
        dialog._remember()
        state=replace(dialog._states[0])
        self.assertEqual(state.key,"diagram")
        self.assertGreater(state.offset,0)
        before=dialog.diagram.mapTo(dialog.panel.scroll.viewport(),QPoint()).y()
        theme.set_text("larger")
        kit.refont(dialog)
        self.settle(dialog)
        self.assertLessEqual(abs(dialog.diagram.mapTo(dialog.panel.scroll.viewport(),QPoint()).y()-before),1)

    def test_all_scenes_fit_largest_text_in_small_window_and_both_themes(self):
        for scheme in ("light","dark"):
            theme.set_mode(scheme)
            theme.set_text("larger")
            for paper in self.papers:
                dialog = self.show(paper)
                kit.refont(dialog)
                for stage in range(4):
                    dialog.set_stage(stage)
                    self.settle(dialog)
                    self.assertEqual((dialog.width(),dialog.height()),(760,480))
                    self.assertLessEqual(dialog.panel.body.width(),760)
                    self.assertGreaterEqual(dialog.diagram.height(),dialog.diagram.heightForWidth(dialog.diagram.width())-1)
                    dialog.diagram.grab()
                    scene = dialog.diagram.last_scene
                    for rect in scene.text_bounds:
                        self.assertGreaterEqual(rect.left(),-1,(paper.paper_id,stage,rect))
                        self.assertLessEqual(rect.right(),dialog.diagram.width()+1,(paper.paper_id,stage,rect))
                        self.assertGreaterEqual(rect.top(),-1,(paper.paper_id,stage,rect))
                        self.assertLessEqual(rect.bottom(),dialog.diagram.height()+1,(paper.paper_id,stage,rect))
                    for cell,ink in scene.glyph_cells:
                        self.assertTrue(cell.adjusted(-1,-1,1,1).contains(ink),(paper.paper_id,stage,cell,ink))
                        self.assertLessEqual(abs(cell.center().y()-ink.center().y()),1)
                    for index,first in enumerate(scene.ink_groups):
                        for second in scene.ink_groups[index+1:]:
                            self.assertFalse(first.adjusted(0.5,0.5,-0.5,-0.5).intersects(second),
                                             (paper.paper_id,stage,first,second))
                    for op in scene.operations:
                        if op[0]!="line":
                            continue
                        segment=QLineF(op[1],op[2])
                        for ink in scene.ink_groups:
                            box=ink.adjusted(1,1,-1,-1)
                            edges=(QLineF(box.topLeft(),box.topRight()),QLineF(box.topRight(),box.bottomRight()),
                                   QLineF(box.bottomRight(),box.bottomLeft()),QLineF(box.bottomLeft(),box.topLeft()))
                            self.assertFalse(any(segment.intersects(edge)[0]==QLineF.IntersectionType.BoundedIntersection for edge in edges),
                                             (paper.paper_id,stage,op,box))
                    for button in dialog.findChildren(QPushButton):
                        if button.isVisibleTo(dialog):
                            self.assertGreaterEqual(button.width(),QFontMetricsF(button.font()).horizontalAdvance(button.text()))
                    self.assertTrue(dialog.close_button.isVisible())
        self.capture_widget.panel.scroll.verticalScrollBar().setValue(0)
        self.settle(self.capture_widget)
        self.assertTrue(self.capture_widget.isVisible())

    def test_diagrams_differ_and_glyphs_stay_centered_in_cells(self):
        operation_sets=[]
        for paper in self.papers:
            dialog=self.show(paper)
            shapes=[]
            for stage in range(4):
                dialog.set_stage(stage)
                self.settle(dialog)
                scene=dialog.diagram.scene()
                shapes.append(tuple(op[0] for op in scene.operations))
                for op in scene.operations:
                    if op[0]=="glyph":
                        bounds=QFontMetricsF(theme.font("body")).tightBoundingRect(op[1]).translated(op[2])
                        self.assertGreaterEqual(bounds.left(),0)
            operation_sets.append(tuple(shapes))
        self.assertEqual(len(set(operation_sets)),5)

    def test_selected_convolution_window_keeps_outline_and_numeric_glyphs(self):
        for mode in ("light","dark"):
            theme.set_mode(mode)
            theme.set_text("larger")
            dialog=self.show(self.papers[0])
            dialog.set_stage(1)
            self.settle(dialog)
            image=dialog.diagram.grab().toImage()
            scene=dialog.diagram.last_scene
            rect=next(op[1] for op in scene.operations if op[0]=="rect")
            edge_x=round(rect.x()+scene.cell*3)
            target=theme.qcolor("link")
            matches=0
            for y in range(round(rect.y())+4,round(rect.y()+scene.cell*3)-4):
                for x in (edge_x-1,edge_x,edge_x+1):
                    color=image.pixelColor(x,y)
                    matches+=sum(abs(a-b) for a,b in zip(color.getRgb()[:3],target.getRgb()[:3]))<50
            self.assertGreater(matches,25)
            first=next(op for op in scene.operations if op[0]=="glyph" and op[1]=="1")
            bounds=QFontMetricsF(theme.font("body")).tightBoundingRect("1").translated(first[2]).toAlignedRect()
            background=theme.qcolor("selection")
            # 가는 숫자의 회색 가장자리도 배경과의 차이로 확인함.
            pixels=sum(sum(abs(a-b) for a,b in zip(image.pixelColor(x,y).getRgb()[:3],background.getRgb()[:3]))>80
                       for x in range(bounds.left(),bounds.right()+1) for y in range(bounds.top(),bounds.bottom()+1))
            self.assertGreater(pixels,10)

    def test_unknown_paper_and_broken_data_do_not_show_empty_figure_as_ready(self):
        unknown=self.show({"id":"not-provided","title":"임시 논문"})
        self.assertIn("아직 제공",unknown.stage_heading.text())
        self.assertFalse(unknown.diagram.isVisible())
        with patch("gui.paper_explainer.load_explanations",side_effect=ValueError("임시 오류")):
            broken=self.show()
        self.assertIn("읽지 못",broken.stage_heading.text())
        self.assertFalse(broken.next.isEnabled())
        self.assertTrue(broken.close_button.isEnabled())

    def test_missing_required_guidance_is_rejected_before_dialog_construction(self):
        raw=json.loads(EXPLANATIONS.read_text())
        for key in ("short_title","axes","idea","boundary","source_url"):
            with self.subTest(key=key),tempfile.TemporaryDirectory() as directory:
                payload=json.loads(json.dumps(raw))
                del payload['explanations'][PAPER_IDS[0]][key]
                path=Path(directory)/'explanations.json'
                path.write_text(json.dumps(payload))
                with self.assertRaises(ValueError):
                    load_explanations(path)

    def test_parent_page_contract_accepts_mapping_id_and_keeps_parent_selection(self):
        parent=QWidget()
        parent.setProperty("selected_role_id","frontend")
        dialog=PaperExplanationDialog({"id":PAPER_IDS[0],"title":"임시 제목"},parent)
        self.windows.extend([dialog,parent])
        self.assertEqual(dialog.paper_id,PAPER_IDS[0])
        dialog.set_stage(3)
        dialog.accept()
        self.assertEqual(parent.property("selected_role_id"),"frontend")

    def test_popup_fades_with_common_curves_and_finishes_only_first_close(self):
        with patch.object(motion,"enabled",True):
            dialog=PaperExplanationDialog(self.papers[0])
            self.windows.append(dialog)
            dialog.show()
            opening=dialog._motion
            opening.pause()
            self.assertEqual(opening.easingCurve().type().name,"InCubic")
            opening.setCurrentTime(opening.duration()//2)
            self.assertGreater(dialog._opacity_effect.opacity(),0)
            self.assertLess(dialog._opacity_effect.opacity(),1)
            image=dialog.grab().toImage()
            colors={image.pixel(x,y) for x in range(0,image.width(),max(1,image.width()//24))
                    for y in range(0,image.height(),max(1,image.height()//16))}
            self.assertGreater(len(colors),2)
            opening.resume()
            opening.setCurrentTime(opening.duration())
            self.assertIsNone(dialog._motion)
            self.assertEqual(dialog._opacity_effect.opacity(),1)
            finished=QSignalSpy(dialog.finished)
            dialog.accept()
            closing=dialog._motion
            closing.pause()
            self.assertEqual(closing.easingCurve().type().name,"OutCubic")
            self.assertTrue(dialog.isVisible())
            self.assertFalse(dialog.isEnabled())
            dialog.reject()
            dialog.close()
            dialog.next.click()
            self.assertFalse(dialog.set_stage(1))
            self.assertEqual(dialog.stage,0)
            self.assertEqual(len(finished),0)
            closing.resume()
            closing.setCurrentTime(closing.duration())
            self.assertEqual(len(finished),1)
            self.assertEqual(dialog.result(),1)
            self.assertFalse(dialog.isVisible())

    def test_popup_titlebar_close_waits_for_fade_and_reduced_reopen_is_opaque(self):
        with patch.object(motion,"enabled",True):
            dialog=PaperExplanationDialog(self.papers[0])
            self.windows.append(dialog)
            dialog.show()
            dialog._motion.setCurrentTime(dialog._motion.duration())
            dialog.close()
            closing=dialog._motion
            closing.pause()
            self.assertTrue(dialog.isVisible())
            self.assertTrue(dialog._closing)
            closing.resume()
            closing.setCurrentTime(closing.duration())
            self.assertFalse(dialog.isVisible())
            self.assertEqual(dialog.result(),0)
            motion.enabled=False
            dialog.show()
            self.assertEqual(dialog._opacity_effect.opacity(),1)
            self.assertIsNone(dialog._motion)
            dialog.accept()
            self.assertFalse(dialog.isVisible())

    def test_reduced_motion_skips_effect_and_ends_active_fades(self):
        with patch.object(motion,"enabled",False):
            dialog=self.show()
            self.assertIsNone(dialog.graphicsEffect())
            dialog.accept()
            self.assertFalse(dialog.isVisible())
            motion.enabled=True
            dialog.show()
            opening=dialog._motion
            opening.pause()
            motion.enabled=False
            opening.resume()
            opening.setCurrentTime(opening.duration()//2)
            self.assertIsNone(dialog._motion)
            self.assertEqual(dialog._opacity_effect.opacity(),1)
            motion.enabled=True
            dialog.reject()
            closing=dialog._motion
            closing.pause()
            motion.enabled=False
            closing.resume()
            closing.setCurrentTime(closing.duration()//2)
            self.assertFalse(dialog.isVisible())
            self.assertIsNone(dialog._motion)

    def test_parent_deletion_cancels_opening_and_closing_callbacks(self):
        with patch.object(motion,"enabled",True):
            for closing in (False,True):
                parent=QWidget()
                dialog=PaperExplanationDialog(self.papers[0],parent)
                try:
                    dialog.show()
                    if closing:
                        dialog._motion.setCurrentTime(dialog._motion.duration())
                        dialog.reject()
                    running=dialog._motion
                    running.pause()
                    finished=QSignalSpy(dialog.finished)
                    sip.delete(parent)
                    self.assertTrue(sip.isdeleted(dialog))
                    self.assertTrue(sip.isdeleted(running))
                    guikit.pump(10)
                    self.assertEqual(len(finished),0)
                finally:
                    if not sip.isdeleted(parent):
                        sip.delete(parent)

    def test_finished_handler_can_delete_parent_during_fade_completion(self):
        with patch.object(motion,"enabled",True):
            parent=QWidget()
            dialog=PaperExplanationDialog(self.papers[0],parent)
            try:
                dialog.show()
                dialog._motion.setCurrentTime(dialog._motion.duration())
                dialog.finished.connect(lambda _:sip.delete(parent))
                dialog.accept()
                running=dialog._motion
                running.setCurrentTime(running.duration())
                self.assertTrue(sip.isdeleted(parent))
                self.assertTrue(sip.isdeleted(dialog))
            finally:
                if not sip.isdeleted(parent):
                    sip.delete(parent)


if __name__=="__main__":
    unittest.main()
