# -*- coding: utf-8 -*-
"""새 디자인 시스템의 부품(gui/kit.py)과 그 규칙. 첫 화면과 웹 면접 준비 화면의 코드가 정한 글자 크기·굵기·간격 값만 쓰는지,
색 쌍의 대비가 기준(글자 4.5:1, 테두리·표시 3:1)을 넘는지, 단추 높이와 줄 높이가 설계값인지 봄. PyQt6 가 없으면 전부 건너뜀."""
import itertools
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests import guikit  # noqa: E402

from PyQt6.QtCore import Qt  # noqa: E402
from PyQt6.QtGui import QColor, QKeyEvent  # noqa: E402
from PyQt6.QtTest import QTest  # noqa: E402
from PyQt6.QtWidgets import QApplication, QWidget  # noqa: E402

from gui import dialogs, kit, theme  # noqa: E402

ROOT = guikit.ROOT
V2_FILES = ("gui/kit.py", "gui/hub_page.py", "gui/web_home.py", "gui/web_mission.py", "gui/web_drill.py", "gui/web_learn.py",
            "gui/web_setup.py", "gui/web_text.py")  # 새 규칙을 따르는 파일
SIZES = {size for size, _, _ in theme.TYPE.values()} | {theme.CODE_PX}
WEIGHTS = {400, 700}
TEXT_BACKS = ("bg", "surface", "surface_raised", "surface_alt", "hover")
WEAK = {"ok": "ok_weak", "retry": "retry_weak", "wrong": "wrong_weak", "info": "info_weak", "selection_ink": "selection",
        "primary_off_ink": "primary_off", "primary_ink": "primary"}


def luminance(value):
    parts = []
    for part in (QColor(value).redF(), QColor(value).greenF(), QColor(value).blueF()):
        parts.append(part / 12.92 if part <= 0.03928 else ((part + 0.055) / 1.055) ** 2.4)
    return 0.2126 * parts[0] + 0.7152 * parts[1] + 0.0722 * parts[2]


def contrast(one, other):
    bright, dark = sorted((luminance(one), luminance(other)), reverse=True)
    return (bright + 0.05) / (dark + 0.05)


def source(path):
    with open(os.path.join(ROOT, path), encoding="utf-8") as handle:
        return handle.read()


def numbers(text):
    return [int(n) for n in re.findall(r"\b(\d+)\b", text)]


class ContrastTest(unittest.TestCase):
    def test_text_roles_read_on_every_background(self):
        """글자 역할은 쓰이는 모든 바탕에서 4.5:1 이상, 옅은 바탕 위의 같은 색 글자도 4.5:1 이상."""
        for scheme, tokens in theme.TOKENS.items():
            for ink in ("ink", "muted", "faint", "link"):
                for back in TEXT_BACKS:
                    self.assertGreaterEqual(contrast(tokens[ink], tokens[back]), 4.5, "%s: %s / %s" % (scheme, ink, back))
            for ink, back in WEAK.items():
                self.assertGreaterEqual(contrast(tokens[ink], tokens[back]), 4.5, "%s: %s / %s" % (scheme, ink, back))
            for ink in ("ok", "retry", "wrong"):
                for back in ("bg", "surface", "surface_alt"):
                    self.assertGreaterEqual(contrast(tokens[ink], tokens[back]), 4.5, "%s: %s / %s" % (scheme, ink, back))

    def test_edges_and_marks_stand_out(self):
        """입력칸 테두리, 초점 테두리, 진행 막대 채움, 주 단추 면, 그래프 색은 바탕과 3:1 이상."""
        for scheme, tokens in theme.TOKENS.items():
            for mark in ("field_edge", "focus", "primary") + theme.SERIES:
                self.assertGreaterEqual(contrast(tokens[mark], tokens["surface"]), 3, "%s: %s / surface" % (scheme, mark))
            self.assertGreaterEqual(contrast(tokens["link"], tokens["track"]), 3, "%s: link / track" % scheme)
            self.assertGreaterEqual(contrast(tokens["field_edge"], tokens["bg"]), 3, "%s: field_edge / bg" % scheme)
            for one, other in itertools.combinations(theme.SERIES, 2):  # 트랙 색끼리도 구분됨
                a, b = QColor(tokens[one]), QColor(tokens[other])
                self.assertGreater(abs(a.hue() - b.hue()), 40, "%s: %s / %s" % (scheme, one, other))


class RuleTest(unittest.TestCase):
    """글자 크기·굵기·간격은 정한 값만 씀(설계 검사 C2, C3, C4)."""

    def test_font_sizes_come_from_the_type_scale(self):
        found = {}
        for path in V2_FILES:
            text = source(path)
            for value in re.findall(r"setPixelSize\((\d+)\)", text) + re.findall(r"font-size:\s*(\d+)px", text):
                found.setdefault(path, set()).add(int(value))
        for value in re.findall(r"font-size:\s*(\d+)px", theme.STYLE_V2):
            found.setdefault("theme.STYLE_V2", set()).add(int(value))
        for path, values in found.items():
            self.assertTrue(values <= SIZES, "%s: %s" % (path, sorted(values - SIZES)))

    def test_weights_are_regular_or_bold(self):
        for value in re.findall(r"font-weight:\s*(\d+)", theme.STYLE_V2):
            self.assertIn(int(value), WEIGHTS)
        for path in V2_FILES:
            for value in re.findall(r"setWeight\((\d+)\)", source(path)):
                self.assertIn(int(value), WEIGHTS, path)

    def test_spacing_uses_the_space_tokens(self):
        allowed = set(theme.SPACE) | {0}
        for path in V2_FILES:
            text = source(path)
            calls = re.findall(r"setContentsMargins\(([^)]*)\)", text) + re.findall(r"setSpacing\(([^)]*)\)", text)
            calls += re.findall(r"addSpacing\(([^)]*)\)", text) + re.findall(r"\bbox\([^,()]+,\s*\(([^)]*)\)", text)
            for call in calls:
                for value in numbers(call):
                    self.assertIn(value, allowed, "%s: %s" % (path, call))

    def test_no_colour_values_outside_theme(self):
        for path in V2_FILES:
            self.assertEqual([], re.findall(r"#[0-9a-fA-F]{6}\b", source(path)), path)


class PartsTest(unittest.TestCase):
    """부품의 크기와 동작."""

    def setUp(self):
        self.root = kit.page(QWidget())
        self.box = kit.box(self.root, (24, 24, 24, 24), 8)
        self.addCleanup(self.root.close)

    def show(self):
        self.root.resize(600, 400)
        self.root.show()
        guikit.pump()

    def test_button_heights_follow_the_scale(self):
        buttons = {scale: kit.button("단추", "primary", scale) for scale in ("l", "m", "s")}
        plain = kit.button("보조", "secondary", "m")
        text = kit.button("글자", "text", "s")
        for widget in list(buttons.values()) + [plain, text]:
            self.box.addWidget(widget)
        self.show()
        self.assertEqual({scale: button.height() for scale, button in buttons.items()}, {"l": 48, "m": 40, "s": 32})
        self.assertEqual((plain.height(), text.height()), (40, 32))
        self.assertEqual(buttons["l"].objectName(), "primary")

    def test_rows_are_56_or_72_high_and_open_on_one_click(self):
        rows = kit.RowList()
        one = rows.add(kit.Row("한 줄", mark=kit.Dot("todo"), data="a"))
        two = rows.add(kit.Row("두 줄", "둘째 줄", "끝", kit.Dot("done"), data="b"))
        inert = rows.add(kit.Row("누를 수 없음", inert=True))
        self.box.addWidget(rows)
        self.show()
        self.assertEqual((one.height(), two.height()), (56, 72))
        opened = []
        two.clicked.connect(lambda: opened.append(two.data))
        guikit.click(two)
        self.assertEqual(opened, ["b"])
        self.assertFalse(inert.chevron.isVisible())
        self.assertEqual(len(rows.lines), 2)
        for key in (Qt.Key.Key_Return, Qt.Key.Key_Space):  # 키로도 열리고, 누르고 있어도 한 번만 열림
            QTest.keyClick(two, key)
        QApplication.sendEvent(two, QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier, "", True))
        self.assertEqual(opened, ["b", "b", "b"])
        inert.clicked.connect(lambda: opened.append("inert"))
        QTest.keyClick(inert, Qt.Key.Key_Return)
        self.assertEqual(opened, ["b", "b", "b"])
        rows.add_more(["준비 중 하나", "준비 중 둘"])
        guikit.pump()
        self.assertEqual(rows.more_btn.text(), "준비 중 2개 보기")
        guikit.click(rows.more_btn)
        self.assertTrue(rows.more_list.isVisible())
        self.assertEqual(rows.more_btn.text(), "접기")
        rows.clear()
        self.assertEqual((rows.rows, rows.more_btn), ([], None))

    def test_check_rows_toggle_from_the_whole_row_and_keep_the_marks(self):
        checks = kit.CheckList()
        checks.set_items([("첫 항목", "필수", "accent", "지난번 표시함", True), ("둘째 항목", "", "", "", False)])
        self.box.addWidget(checks)
        self.show()
        changed = []
        checks.changed.connect(lambda: changed.append(checks.marks()))
        self.assertEqual(checks.marks(), [1, 0])
        guikit.click(checks.rows[1])
        self.assertEqual(checks.marks(), [1, 1])
        checks.rows[0].setFocus()
        QTest.keyClick(checks.rows[0], Qt.Key.Key_Space)
        self.assertEqual(checks.marks(), [0, 1])
        self.assertEqual(len(changed), 2)
        checks.set_enabled(False)
        guikit.click(checks.rows[1])
        self.assertEqual(checks.marks(), [0, 1])  # 꺼진 목록은 바뀌지 않음
        self.assertGreaterEqual(checks.rows[0].height(), 48)
        self.assertTrue(checks.rows[0].tag.isVisible())
        self.assertFalse(checks.rows[1].tag.isVisible())

    def test_tabs_pick_one_and_report_the_number(self):
        tabs = kit.TabBar(["해설", "비교", "점검"])
        self.box.addWidget(tabs)
        self.show()
        picked = []
        tabs.picked.connect(picked.append)
        guikit.click(tabs.buttons[2])
        self.assertEqual(picked, [2])
        self.assertTrue(tabs.buttons[2].isChecked())
        self.assertFalse(tabs.buttons[0].isChecked())
        self.assertEqual(tabs.buttons[0].height(), 48)

    def test_next_card_has_the_only_primary_button(self):
        card = kit.NextCard()
        card.set_item("거래내역 불러오기", "라이브 코딩 미션 · 1단계 · 34분 남음", "이어 하기")
        self.box.addWidget(card)
        self.box.addWidget(kit.button("보조", "secondary", "l"))
        self.show()
        self.assertEqual(kit.visible_primary_buttons(self.root), [card.button])
        self.assertEqual(card.button.height(), 48)
        card.set_item("끝", "", "")
        self.assertFalse(card.button.isVisibleTo(self.root))

    def test_stepper_and_dots_paint_every_state(self):
        stepper = kit.Stepper()
        stepper.set_steps([(0, "코드 설명", "done"), (1, "세 가지 화면", "now"), (2, "건너뜀", "skip"), (3, "", "lock")])
        self.box.addWidget(stepper)
        for state in ("progress", "review", "done", "todo", "ready", "series_web"):
            self.box.addWidget(kit.Dot(state))
        self.show()
        image = stepper.grab().toImage()
        self.assertEqual(stepper.height(), theme.CONTROL["stepper"] - 1)
        colors = {image.pixelColor(x, image.height() // 2).name() for x in range(0, image.width(), 2)}
        self.assertIn(theme.color("primary"), colors)  # 지금 단계의 원
        self.assertIn(theme.color("link"), colors)  # 끝난 구간의 선
        middle, link = image.height() // 2, theme.color("link")
        background = image.pixelColor(0, 1).name()
        line = [x for x in range(image.width()) if image.pixelColor(x, middle).name() == link and image.pixelColor(x, middle - 6).name() == background]
        self.assertTrue(line)
        shades = {image.pixelColor(x, y).name() for x in line for y in range(middle - 3, middle + 4)} - {background}
        self.assertEqual(shades, {link})  # 2px 연결선이 반 화소로 번진 옅은 줄 없이 그려짐
        for dot in self.root.findChildren(kit.Dot):
            middle = dot.grab().toImage().pixelColor(kit.MARK // 2, kit.MARK // 2).name()
            edge = dot.grab().toImage().pixelColor(kit.MARK // 2, kit.MARK // 2 - 4).name()
            token = theme.color(kit.DOT_STATES.get(dot.state, dot.state))
            if dot.state == "todo":  # 테두리만 칠하고 가운데는 비움
                self.assertEqual(edge, token)
                self.assertNotEqual(middle, token)
            elif dot.state != "done":  # done 은 가운데에 체크를 그림
                self.assertEqual(middle, token, dot.state)

    def test_para_grows_with_its_text_and_keeps_px_line_height(self):
        text = kit.para("긴 안내 글입니다. " * 20)
        short = kit.label("짧은 글", "caption", "secondary")
        self.box.addWidget(text)
        self.box.addWidget(short)
        self.show()
        guikit.pump()
        self.assertEqual((text.line, text.font().pixelSize()), (28, 17))
        self.assertGreater(text.height(), 28 * 3)
        self.assertEqual(short.property("tone"), "secondary")
        self.assertEqual(short.font().pixelSize(), 14)
        text.setText("한 줄 글")  # 폭이 그대로여도 긴 글의 높이가 남지 않음
        guikit.pump()
        self.assertLessEqual(max(text.heightForWidth(text.width()), text.minimumSizeHint().height()), 28)

    def test_code_fields_keep_the_code_font_size(self):
        """새 화면의 입력칸 규칙이 글자 크기를 정하지 않아, 코드 칸(원문 상자, 비교, 설치 로그)에 준 코드 글꼴 크기가 남음."""
        from PyQt6.QtWidgets import QPlainTextEdit
        edit = QPlainTextEdit("const a = 1")
        edit.setObjectName("plain")
        edit.setFont(theme.code_font(-1))
        self.box.addWidget(edit)
        self.show()
        self.assertEqual(edit.font().pixelSize(), theme.code_font(-1).pixelSize())

    def test_message_dialog_roles(self):
        """되돌릴 수 없는 확인 창은 오른쪽 끝이 빨간 옅은 단추이고 Enter 로 눌리지 않음. 안내 창의 확인 단추는 Enter 로 눌림."""
        ask = dialogs.MessageDialog(None, "실전 끝내기", "지금 코드로 마지막 검사를 합니다.", (("끝내기", "finish", "danger"), ("닫기", "")))
        ask.show()
        guikit.pump()
        self.addCleanup(ask.close)
        self.assertEqual(ask.buttons["finish"].objectName(), "danger")
        self.assertEqual(ask.buttons[""].objectName(), "")
        self.assertFalse(ask.buttons["finish"].isDefault())
        self.assertEqual(ask.property("ui"), "2")
        self.assertEqual(ask.buttons["finish"].height(), 48)
        self.assertGreater(ask.buttons["finish"].x(), ask.buttons[""].x())
        plain = dialogs.MessageDialog(None, "알림", "글")
        plain.show()
        guikit.pump()
        self.addCleanup(plain.close)
        self.assertEqual(plain.buttons["ok"].objectName(), "primary")
        self.assertTrue(plain.buttons["ok"].isDefault())
        self.assertLessEqual(plain.width(), 560)
        self.assertGreaterEqual(plain.width(), 480)

    def test_message_dialog_buttons_keep_their_whole_label(self):
        """글자가 긴 단추도 잘리지 않음. 한 줄에 들어가지 않으면 한 줄에 하나씩 쌓고 첫 번째(주 단추)를 위에 둠."""
        long = (("다른 컴퓨터의 풀이 가져오기", "remote"), ("이 컴퓨터 풀이로 올리기", "local"), ("나중에 정하기", ""))
        for buttons, detail in ((long, "자세한 출력"), ((("다시 찾기", "find"), ("Node 위치 지정…", "pick"), ("닫기", "")), "")):
            ask = dialogs.MessageDialog(None, "알림", "글", buttons, detail=detail)
            ask.show()
            guikit.pump()
            self.addCleanup(ask.close)
            self.assertLessEqual(ask.width(), 560)
            for button in ask.buttons.values():
                self.assertTrue(button.isVisible())
                self.assertGreaterEqual(button.width(), button.sizeHint().width(), button.text())
                self.assertLessEqual(button.geometry().right(), ask.width() - 32)
        stacked = [ask_button.y() for ask_button in self.stacked(long)]
        self.assertEqual(stacked, sorted(stacked))  # 첫 번째 단추가 맨 위

    def stacked(self, buttons):
        ask = dialogs.MessageDialog(None, "알림", "글", buttons)
        ask.show()
        guikit.pump()
        self.addCleanup(ask.close)
        return [ask.buttons[item[1]] for item in buttons]


if __name__ == "__main__":
    unittest.main()
