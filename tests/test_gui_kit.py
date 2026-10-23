# -*- coding: utf-8 -*-
"""새 디자인 시스템의 부품(gui/kit.py)과 그 규칙. 첫 화면과 웹 면접 준비 화면의 코드가 정한 글자 크기·굵기·간격 값만 쓰는지,
색 쌍의 대비가 기준(글자 4.5:1, 테두리·표시 3:1)을 넘는지, 단추 높이와 줄 높이가 설계값인지 봄. PyQt6 가 없으면 전부 건너뜀."""
import itertools
import os
import re
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests import guikit  # noqa: E402

from PyQt6.QtCore import QBuffer, QByteArray, QEvent, QIODevice, QObject, QPoint, QSettings, Qt  # noqa: E402
from PyQt6.QtGui import QColor, QKeyEvent, QPixmap  # noqa: E402
from PyQt6.QtTest import QTest  # noqa: E402
from PyQt6.QtWidgets import QApplication, QWidget  # noqa: E402

from gui import dialogs, kit, theme  # noqa: E402
from gui.docview import FigureView  # noqa: E402
from gui.journey_map import COLUMNS, PILL_GAP, MapView  # noqa: E402
from journey import bank  # noqa: E402

ROOT = guikit.ROOT
V2_FILES = ("gui/kit.py", "gui/hub_page.py", "gui/web_home.py", "gui/web_mission.py", "gui/web_drill.py", "gui/web_learn.py",
            "gui/web_setup.py", "gui/web_text.py", "gui/journey_map.py", "gui/journey_page.py", "gui/journey_result.py",
            "gui/journey_text.py", "gui/cases_dialog.py", "gui/docview.py")  # 새 규칙을 따르는 파일
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


def sizes():
    """지금 글자 크기 단계에서 쓸 수 있는 글자 크기."""
    return {size for size, _, _ in theme.TYPE.values()} | {theme.CODE_PX}


def map_rows():
    """dungeons/index.json 의 던전 16개로 만든 지도 줄. 던전 1 은 클리어, 2 는 진행 중, 3 은 시작 전, 4 부터는 준비 중."""
    rows = []
    for number, entry in enumerate(bank.read_index(os.path.join(ROOT, "dungeons"))):
        rows.append(dict(entry, ready=number < 3, error="", cleared=number == 0, passed=(6, 2, 0)[number] if number < 3 else 0,
                         total=6 if number < 3 else 0))
    return rows


class WindowSpy(QObject):
    """따로 창으로 뜨는 위젯의 이름을 shown 에 모음."""

    def __init__(self, shown):
        super().__init__()
        self.shown = shown

    def eventFilter(self, target, event):
        if event.type() == QEvent.Type.Show and target.isWidgetType() and target.isWindow():
            self.shown.append(type(target).__name__)
        return False


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
        for step in theme.TEXT_STEPS:  # 단추 글자와 꼬리표 높이는 스타일시트가 단계마다 TYPE 에서 채움
            theme.set_text(step)
            self.addCleanup(theme.set_text, "normal")
            sheet = theme.STYLE_V2 % theme.style_tokens("light")
            values = {int(value) for value in re.findall(r"font-size:\s*(\d+)px", sheet)}
            self.assertTrue(values and values <= sizes(), "theme.STYLE_V2 %s: %s" % (step, sorted(values - sizes())))
            self.assertIn("max-height: %dpx" % (theme.TYPE["caption"][1] + 2), sheet)
        theme.set_text("normal")
        for path, values in found.items():
            self.assertTrue(values <= sizes(), "%s: %s" % (path, sorted(values - sizes())))

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

    def test_journey_css_colours_are_plain_values(self):
        """여행 문서와 결과 칸 CSS 의 글자·바탕 색은 #rrggbb 나 transparent 만 씀(설계 10.1-23). doc_css 의 줄 간격 키 line 이
        같은 이름의 색 토큰을 가리므로 %(line)s 를 색으로 쓰면 116 이 들어가고 Qt 는 그 규칙을 말없이 버림."""
        mode = theme.state["mode"]
        self.addCleanup(theme.set_mode, mode)
        for scheme in ("light", "dark"):
            theme.set_mode(scheme)
            for name, css in (("journey_css", theme.journey_css()), ("result_css", theme.result_css())):
                values = re.findall(r"(?<![\w-])(?:background-)?color\s*:\s*([^;}]+)", css)
                self.assertTrue(values, name)
                for value in values:
                    self.assertRegex(value.strip(), r"\A(#[0-9a-f]{6}|transparent)\Z", "%s %s" % (scheme, name))


class TextStepTest(unittest.TestCase):
    """글자 크기 단계. 크게는 모든 크기 +2, 더 크게는 +4 이고 줄 높이는 비례해 키워 4 단위에 맞춤."""

    def test_steps_add_px_and_keep_line_heights_on_the_grid(self):
        self.assertEqual(theme.scaled_type("normal"), theme.BASE_TYPE)
        for step, extra in theme.TEXT_PX.items():
            scaled = theme.scaled_type(step)
            for role, (size, line, weight) in theme.BASE_TYPE.items():
                grown, grown_line, grown_weight = scaled[role]
                self.assertEqual((grown, grown_weight), (size + extra, weight), role)
                if extra:
                    self.assertEqual(grown_line % 4, 0, role)
                    self.assertTrue(grown + 3 <= grown_line <= grown * 2, (step, role, scaled[role]))
                    self.assertGreaterEqual(grown_line, line, role)
        self.assertEqual((theme.scaled_type("large")["body"], theme.scaled_type("larger")["body"]), ((19, 32, 400), (21, 36, 400)))
        self.assertEqual((theme.scaled_type("large")["headline"], theme.scaled_type("larger")["caption"]), ((24, 32, 700), (18, 28, 400)))

    def test_set_text_changes_type_and_falls_back_to_the_default(self):
        self.addCleanup(theme.set_text, "normal")
        self.assertTrue(theme.set_text("larger"))
        self.assertEqual((theme.state["text"], theme.TYPE["body"], theme.text_px(), theme.font("body").pixelSize()), ("larger", (21, 36, 400), 4, 21))
        self.assertFalse(theme.set_text("larger"))
        self.assertTrue(theme.set_text("huge"))
        self.assertEqual(theme.state["text"], theme.TEXT_DEFAULT)
        self.assertIn("body { font-size: 19px; }", theme.web_css())  # 문서 본문도 단계를 따름
        theme.set_text("normal")
        self.assertEqual((theme.TYPE, theme.text_px()), (theme.BASE_TYPE, 0))


class PartsTest(unittest.TestCase):
    """부품의 크기와 동작. 보통 글자에서 봄."""

    def setUp(self):
        self.addCleanup(theme.set_text, theme.state["text"])
        theme.set_text("normal")
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

    def test_lock_dot_draws_a_padlock_in_the_mark_box(self):
        """잠김 점은 점 칸 20 안에 높이 16(2~18)의 자물쇠를 그림. faint 색 2px 고리와 그 아래 채운 몸통이 있고 고리 안은 비어 있음."""
        lock = kit.Dot("lock")
        self.box.addWidget(lock)
        self.show()
        image = lock.grab().toImage()
        faint, back = theme.color("faint"), image.pixelColor(0, 0).name()
        self.assertEqual((lock.width(), lock.height()), (kit.MARK, kit.MARK))
        for x, y in ((10, 14), (6, 16), (13, 11), (10, 3), (6, 8), (13, 8)):  # 몸통, 고리 꼭대기, 고리 양옆
            self.assertEqual(image.pixelColor(x, y).name(), faint, (x, y))
        self.assertNotEqual(image.pixelColor(10, 7).name(), faint)  # 고리 안
        for y in (0, 1, 18, 19):
            self.assertEqual({image.pixelColor(x, y).name() for x in range(kit.MARK)}, {back}, y)

    def test_new_rows_open_no_window_of_their_own(self):
        """목록 줄을 만들 때 부모 없는 글자나 꺾쇠가 잠깐 따로 창으로 뜨지 않음. 뜨면 화면의 창이 초점을 잃어 키보드로 고르던 것이 끊김."""
        rows = kit.RowList()
        self.box.addWidget(rows)
        self.show()
        shown = []
        spy = WindowSpy(shown)
        guikit.APP.installEventFilter(spy)
        self.addCleanup(guikit.APP.removeEventFilter, spy)
        rows.add(kit.Row("제목", "둘째 줄", "끝", kit.Dot("todo"), data="a"))
        rows.add(kit.Row("잠김", "여는 조건", "보스", kit.Dot("lock"), inert=True))
        guikit.pump()
        self.assertEqual([], shown)
        self.assertEqual([True, True, True], [part.isVisible() for part in (rows.rows[0].second, rows.rows[0].end, rows.rows[0].chevron)])
        self.assertFalse(rows.rows[1].chevron.isVisible())

    def test_new_parts_open_no_window_of_their_own(self):
        """제목 있는 위 막대, 꼬리표와 메모가 있는 체크 줄, 캡션 있는 그림도 만들 때 따로 창으로 뜨지 않음."""
        self.show()
        shown = []
        spy = WindowSpy(shown)
        guikit.APP.installEventFilter(spy)
        self.addCleanup(guikit.APP.removeEventFilter, spy)
        picture = QPixmap(40, 20)
        picture.fill(QColor("#336699"))
        data = QByteArray()
        buffer = QBuffer(data)
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        picture.save(buffer, "PNG")
        parts = [kit.TopBar("← 처음 화면", "제목"), kit.Check("글", "필수", "accent", "메모"), FigureView("", "그림 1. 캡션", data=bytes(data))]
        for part in parts:
            self.box.addWidget(part)
        guikit.pump()
        self.assertEqual([], shown)
        self.assertEqual([True] * 4, [part.isVisible() for part in (parts[0].title, parts[1].tag, parts[1].note, parts[2].caption)])

    def test_map_draws_round_nodes_name_pills_and_a_focus_ring(self):
        """던전 지도(gui/journey_map.MapView). 높이는 caption 줄 높이로 정하고(보통 370, 크게 378) 원 지름은 40. 이름 알약은 caption 줄
        높이이고 길보다 위에 surface 로 칠함. 바깥 열 이름 글은 [24, 폭 − 24] 안. 고른 원의 고리는 키보드 초점이면 focus 색, 아니면 ink.
        이름 알약을 눌러도 고름. 1024 창의 지도 폭(377)에서 이웃 알약 사이가 PILL_GAP 이상이고, 줄임표로 줄인 이름은 보통에서 하나,
        크게에서 셋."""
        for step, height, short in (("normal", 370, ["연결과 순서의 다리"]), ("large", 378, ["기억의 도서관", "연결과 순서의 다리", "속삭이는 사전"])):
            theme.set_text(step)
            root = kit.page(QWidget())
            self.addCleanup(root.close)
            box = kit.box(root)
            view = MapView()
            view.setFixedWidth(377)
            view.set_rows(map_rows(), "d01")
            box.addWidget(view)
            root.show()
            root.activateWindow()
            guikit.pump()
            view.clearFocus()  # 창이 켜질 때 첫 초점을 받으므로 먼저 뺌
            guikit.pump()
            self.assertEqual(view.height(), height, step)
            image = view.grab().toImage()
            center = view.nodes()[0][1].center().toPoint()
            filled = [x for x in range(center.x() - 30, center.x() + 30) if guikit.near(image.pixelColor(x, center.y()), "ok")]
            self.assertTrue(38 <= filled[-1] - filled[0] + 1 <= 40, (step, filled))  # 가운데 번호 글자는 빼고 양 끝 사이를 잼
            self.assertTrue(guikit.near(image.pixelColor(center.x() + 24, center.y()), "ink"), (step, image.pixelColor(center.x() + 24, center.y()).name()))
            labels = view.labels()
            self.assertEqual({round(pill.height()) for _, pill, _, _ in labels}, {theme.TYPE["caption"][1]}, step)
            turn = view.nodes()[3][1].center()  # 넷째 던전에서 다섯째로 꺾는 세로 길이 넷째 이름 밑으로 지나감
            pill = labels[3][1]
            self.assertTrue(guikit.near(image.pixelColor(round(turn.x()), round(pill.top()) + 1), "surface"), step)
            for index, (_, _, text, _) in enumerate(labels):
                if MapView.spot(index)[1] in (0, COLUMNS - 1):
                    self.assertGreaterEqual(text.left(), 24, (step, index))
                    self.assertLessEqual(text.right(), view.width() - 24, (step, index))
            for line in range(4):
                pills = sorted((pill for index, (_, pill, _, _) in enumerate(labels) if MapView.spot(index)[0] == line), key=lambda p: p.left())
                for one, other in zip(pills, pills[1:]):
                    self.assertGreaterEqual(other.left() - one.right(), PILL_GAP, (step, line))
            self.assertEqual([row["title"] for row, (_, _, _, name) in zip(view.rows, labels) if name != row["title"]], short, step)
            self.assertEqual([], [name for _, _, _, name in labels if name.endswith(" …")], "줄임표 앞에 띄어쓰기가 남지 않음")
            picked = []
            view.picked.connect(picked.append)
            name = labels[5][1]
            QTest.mouseClick(view, guikit.LEFT, pos=QPoint(round(name.right()) - 3, round(name.center().y())))
            self.assertEqual(picked, ["d06"], step)
            view.set_selected("d01")
            view.clearFocus()
            view.setFocus(Qt.FocusReason.TabFocusReason)  # 마우스로 누른 초점은 글자색 고리라 키보드 초점으로 다시 줌
            guikit.pump()
            self.assertTrue(view.hasFocus(), step)
            image = view.grab().toImage()
            self.assertTrue(guikit.near(image.pixelColor(center.x() + 24, center.y()), "focus"), step)

    def test_splitter_keeps_and_remembers_the_ratio(self):
        """끌어 옮기는 칸 나누기의 손잡이 폭은 24(세로 나누기 16)이고 가운데에 무늬가 있음. 가로 칸은 320 아래로 줄지 않음. 옮긴 몫은 설정에
        0~1 값으로 남고 창이 커져도 그 몫을 지킴. 같은 key 로 다시 만들면 그 몫으로 시작함. 두 번 누르면 처음 몫으로 돌아감.
        잠그면 끌리지 않고 무늬가 사라짐."""
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder, True)
        settings = QSettings(os.path.join(folder, "split.ini"), QSettings.Format.IniFormat)
        wide = kit.splitter(Qt.Orientation.Horizontal, "test/split", 0.5, settings=settings)
        tall = kit.splitter(Qt.Orientation.Vertical, "test/split_v", 340 / 608, 16, settings)
        for split in (wide, tall):
            split.addWidget(QWidget())
            split.addWidget(QWidget())
            self.box.addWidget(split, 1)
        self.root.resize(900, 700)
        self.root.show()
        guikit.pump()
        handle = wide.handle(1)
        self.assertEqual((handle.width(), tall.handle(1).height()), (24, 16))
        self.assertEqual((wide.widget(0).minimumWidth(), tall.widget(0).minimumHeight()), (kit.PANE_MIN, 0))
        self.assertLessEqual(abs(wide.sizes()[0] - wide.sizes()[1]), 1)
        self.assertAlmostEqual(tall.sizes()[0] / sum(tall.sizes()), 340 / 608, delta=0.01)
        middle = QPoint(handle.width() // 2, handle.height() // 2)
        self.assertEqual(handle.grab().toImage().pixelColor(middle).name(), theme.color("border"))
        self.assertEqual(handle.grab().toImage().pixelColor(2, 2).name(), theme.color("bg"))
        QTest.mouseMove(handle, middle)  # 올리면 무늬가 짙어짐
        guikit.pump()
        self.assertEqual(handle.grab().toImage().pixelColor(middle).name(), theme.color("scroll_hover"))
        guikit.drag(handle, -100)
        ratio = wide.sizes()[0] / sum(wide.sizes())
        self.assertLess(ratio, 0.45)
        self.assertAlmostEqual(float(settings.value("test/split")), ratio, places=3)
        self.root.resize(1300, 700)
        guikit.pump()
        self.assertAlmostEqual(wide.sizes()[0] / sum(wide.sizes()), ratio, delta=0.005)
        self.assertAlmostEqual(kit.splitter(Qt.Orientation.Horizontal, "test/split", 0.5, settings=settings).ratio, ratio, places=3)
        QTest.mouseDClick(wide.handle(1), guikit.LEFT, Qt.KeyboardModifier.NoModifier, middle)
        guikit.pump()
        self.assertLessEqual(abs(wide.sizes()[0] - wide.sizes()[1]), 1)
        self.assertEqual(float(settings.value("test/split")), 0.5)
        before = wide.sizes()
        wide.set_locked(True)
        guikit.drag(wide.handle(1), -150)
        self.assertEqual(wide.sizes(), before)
        self.assertEqual(float(settings.value("test/split")), 0.5)
        self.assertEqual(wide.handle(1).grab().toImage().pixelColor(middle).name(), theme.color("bg"))
        self.assertEqual(wide.handle(1).cursor().shape(), Qt.CursorShape.ArrowCursor)
        wide.set_locked(False)
        guikit.drag(wide.handle(1), -150)
        self.assertLess(wide.sizes()[0], before[0])
        self.assertEqual(wide.handle(1).cursor().shape(), Qt.CursorShape.SplitHCursor)
        for bad in ("넓게", 1.5, 0):  # 0~1 사이의 수가 아니면 처음 몫으로 시작함
            settings.setValue("test/split", bad)
            self.assertEqual(kit.splitter(Qt.Orientation.Horizontal, "test/split", 0.5, settings=settings).ratio, 0.5)
        self.assertEqual(kit.splitter(Qt.Orientation.Horizontal, ratio=0.4).ratio, 0.4)  # 설정이 없으면 기억하지 않음

    def test_banner_action_sits_right_of_the_text(self):
        """띠의 행동 단추는 글 오른쪽의 보조 단추 m 임(높이 40, 크게에서도 40 이고 글자 19). 바탕은 띠 바탕과 구분되는 surface 이고
        꺼지면 띠가 비치며 글만 faint 가 됨. 글이 한 줄이면 단추와 같은 가운데 높이에 옴. 두 줄이면 앞 낱말이 첫 줄에 붙고 글이 잘리지 않음.
        단추가 없는 띠의 action 은 None."""
        plain = kit.banner("단추 없는 띠입니다.", "warning")
        one = kit.banner("보스 문제가 열렸습니다.", "success", action="보스 풀기")
        two = kit.banner("처음으로 통과했습니다. 해설이 열렸습니다. " * 3, "success", action="해설 보기")
        for banner in (plain, one, two):
            self.box.addWidget(banner)
        self.box.addStretch(1)
        self.root.resize(600, 500)
        self.root.show()
        guikit.pump()
        self.assertIsNone(plain.action)
        for banner in (one, two):
            button = banner.action
            self.assertEqual((button.height(), button.objectName(), button.property("scale")), (40, "", "m"))
            self.assertGreater(button.x(), banner.text.mapTo(banner, QPoint(banner.text.width(), 0)).x())
            image = banner.grab().toImage()
            self.assertEqual(image.pixelColor(button.x() + 8, button.y() + 20).name(), theme.color("surface"))
            self.assertEqual(image.pixelColor(4, banner.height() // 2).name(), theme.color("ok_weak"))
        self.assertLessEqual(abs(one.text.mapTo(one, QPoint(0, one.text.height() // 2)).y() - (one.action.y() + 20)), 2)
        self.assertEqual(one.height(), 12 + 40 + 12)
        self.assertGreaterEqual(two.text.height(), two.text.heightForWidth(two.text.width()))
        self.assertGreater(two.text.height(), 40)
        self.assertEqual(two.word.mapTo(two, QPoint(0, 0)).y(), two.text.mapTo(two, QPoint(0, 0)).y())
        one.action.setEnabled(False)
        guikit.pump()
        image = one.grab().toImage()
        button = one.action.geometry()
        self.assertEqual(image.pixelColor(button.x() + 8, button.y() + 20).name(), theme.color("ok_weak"))
        self.assertEqual(guikit.ink(image, theme.color("ok_weak"), button.adjusted(12, 8, -12, -8)).name(), theme.color("faint"))
        theme.set_text("large")
        kit.refont(self.root)
        guikit.pump()
        self.assertEqual((one.action.height(), one.action.font().pixelSize()), (40, 19))

    def test_chips_on_the_background_and_switched_off(self):
        """바탕 위 칩(onbg)은 높이 40 이고 평소에는 바탕이 비치며 고르면 흰 알약(surface)이 됨. 꺼진 칩은 고른 알약을 남기고 글만
        faint 로 바뀜. 표준 칩과 바탕 위 칩의 고름·안 고름 넷을 밝게·어둡게에서 봄."""
        self.addCleanup(theme.set_mode, "light")
        chips = {}
        for onbg in (False, True):
            for checked in (False, True):
                for enabled in (True, False):
                    chip = kit.chip("Python", onbg=onbg)
                    chip.setChecked(checked)
                    chip.setEnabled(enabled)
                    self.box.addWidget(chip, 0, Qt.AlignmentFlag.AlignLeft)
                    chips[onbg, checked, enabled] = chip
        self.root.resize(600, 520)
        self.show()
        backs = {(False, False): "surface_alt", (False, True): "selection", (True, False): "bg", (True, True): "surface"}
        offs = {(False, False): "primary_off", (False, True): "selection", (True, False): "bg", (True, True): "surface"}
        for scheme in ("light", "dark"):
            theme.set_mode(scheme)
            guikit.pump()
            image = self.root.grab().toImage()
            for (onbg, checked, enabled), chip in chips.items():
                where = (scheme, onbg, checked, enabled)
                self.assertEqual(chip.height(), 40, where)
                self.assertEqual(chip.property("onbg"), True if onbg else None, where)
                box = chip.geometry()
                back = theme.color((backs if enabled else offs)[onbg, checked])
                self.assertEqual(image.pixelColor(box.x() + 8, box.y() + 20).name(), back, where)
                if not enabled:
                    self.assertEqual(guikit.ink(image, back, box.adjusted(16, 8, -16, -8)).name(), theme.color("faint"), where)

    def test_flat_scroll_area_in_a_card_keeps_the_round_corners(self):
        """카드 끝까지 닿는 스크롤 칸은 flat 이면 바탕을 칠하지 않아 카드의 둥근 모서리가 보임. flat 이 아니면 칸 바탕(surface)이 모서리를 덮음."""
        from gui.docview import DocView
        views = {}
        for flat in (True, False):
            card, card_box = kit.card(0, 0)
            view = DocView(flat=flat)
            view.set_markdown("본문 문단", "", "python")
            card_box.addWidget(view)
            self.box.addWidget(card, 1)
            views[flat] = card
        self.root.resize(500, 500)
        self.show()
        image = self.root.grab().toImage()
        for flat, card in views.items():
            box = card.geometry()
            corners = {image.pixelColor(x, y).name() for x, y in ((box.left() + 1, box.top() + 1), (box.right() - 1, box.top() + 1),
                                                                (box.left() + 1, box.bottom() - 1), (box.right() - 1, box.bottom() - 1))}
            self.assertEqual(corners, {theme.color("bg" if flat else "surface")}, flat)
            self.assertEqual(image.pixelColor(box.center()).name(), theme.color("surface"), flat)

    def test_code_editor_keeps_a_small_find_bar_and_a_round_corner(self):
        """새 규칙 안의 편집기는 모서리가 12 이고 줄 번호 칸이 그 모서리 밖으로 나오지 않음. 찾기 막대는 입력칸·단추 규칙(46·36)을
        받지 않아 높이가 40 이하이고 단추 글자는 코드 크기(보통 15, 크게 17)임."""
        from gui.editor import CodeEditor, FindBar
        editor = CodeEditor()
        editor.setPlainText("answer = 0\n" * 30)
        self.box.addWidget(editor)
        bar = FindBar(editor, self.root)
        self.show()
        for step in ("normal", "large"):
            theme.set_text(step)
            bar.reveal()
            guikit.pump()
            self.assertLessEqual(bar.height(), 40, step)
            self.assertEqual(bar.prev_btn.font().pixelSize(), theme.TYPE["code"][0], step)
            bar.dismiss()
        guikit.pump()
        image = self.root.grab().toImage()
        box = editor.geometry()
        for x, y in ((box.left() + 2, box.top() + 2), (box.left() + 2, box.bottom() - 2), (box.right() - 2, box.top() + 2)):
            self.assertEqual(image.pixelColor(x, y).name(), theme.color("bg"), (x, y))  # 모서리 6 이면 편집기 색
        self.assertEqual(image.pixelColor(box.left() + 4, box.top() + 20).name(), theme.EDITOR["gutter"])

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

    def test_para_in_a_card_gets_its_whole_wrapped_height(self):
        """카드 안에 겹친 상자에서도 긴 글이 줄바꿈한 높이를 다 받음. Para 의 최소 높이 알림이 꺼지면 아래가 잘림."""
        card, card_box = kit.card(24, 8)
        text = kit.para("긴 안내 글입니다. " * 30)
        card_box.addWidget(text)
        self.box.addWidget(card)
        self.box.addStretch(1)
        self.root.resize(420, 300)  # 글이 다 들어가기에 모자란 높이를 달라고 해도 창이 글 높이만큼은 커져야 함
        self.root.show()
        guikit.pump()
        self.assertGreaterEqual(text.height(), text.heightForWidth(text.width()))

    def test_refont_follows_the_text_step(self):
        """글자 크기 단계를 바꾼 뒤 refont 가 문단·이름표·목록 줄·꼬리표·시계·체크 상자의 글꼴과 크기를 지금 단계로 다시 줌."""
        text = kit.para("긴 안내 글입니다. " * 10)
        short = kit.label("짧은 글", "caption", "secondary")
        rows = kit.RowList()
        row = rows.add(kit.Row("제목", "둘째 줄"))
        tag = kit.badge("통과", "success")
        clock_box, _, num = kit.clock()
        checks = kit.CheckList()
        checks.set_items([("항목", "", "", "", False)])
        for widget in (text, short, rows, tag, clock_box, checks):
            self.box.addWidget(widget)
        self.show()
        narrow = num.minimumWidth()
        theme.set_text("larger")
        kit.refont(self.root)
        guikit.pump()
        self.assertEqual((text.font().pixelSize(), text.line, short.font().pixelSize()), (21, 36, 18))
        self.assertEqual((row.title.font().pixelSize(), row.title.height(), row.second.height()), (21, 28, 28))
        self.assertEqual((tag.font().pixelSize(), tag.height(), checks.rows[0].box.height()), (18, 30, 36))
        self.assertGreater(num.minimumWidth(), narrow)
        self.assertGreater(text.height(), 36 * 3)
        theme.set_text("normal")
        kit.refont(self.root)
        guikit.pump()
        self.assertEqual((text.font().pixelSize(), text.line, row.title.height(), tag.height(), num.minimumWidth()), (17, 28, 24, 24, narrow))

    def test_web_documents_use_the_type_scale(self):
        """웹 문서의 본문·제목·코드 글자가 설계 크기(17·22·15)이고, 코드 상자 칸은 둥근 바탕을 덮지 않게 투명함."""
        import mdlite
        from gui.docview import TextPiece
        piece = TextPiece(mdlite.to_html("# 제목\n\n본문 문단\n\n```js\nconst a = 1;\n```\n"), theme.web_css())
        sizes = {}
        block = piece.document().begin()
        while block.isValid():
            if block.text().strip():
                sizes[block.text()] = block.begin().fragment().charFormat().font().pixelSize()
            block = block.next()
        self.assertEqual((sizes["제목"], sizes["본문 문단"], sizes["const a = 1;"]),
                         (theme.TYPE["headline"][0], theme.TYPE["body"][0], theme.TYPE["code"][0]))
        self.assertIn("td.codebox { background-color: transparent;", theme.web_css().split("body { font-size: 17px; }")[1])

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
        """글자가 긴 단추도 어느 글자 크기에서나 잘리지 않음. 한 줄에 들어가지 않으면 한 줄에 하나씩 쌓고 첫 번째(주 단추)를 위에 둠."""
        long = (("다른 컴퓨터의 풀이 가져오기", "remote"), ("이 컴퓨터 풀이로 올리기", "local"), ("나중에 정하기", ""))
        three = (("이어서 하기", "resume"), ("처음부터 다시 받기", "again", "danger_text"), ("닫기", ""))
        self.addCleanup(theme.set_text, "normal")
        for step in theme.TEXT_STEPS:
            theme.set_text(step)
            for buttons, detail in ((long, "자세한 출력"), ((("다시 찾기", "find"), ("Node 위치 지정…", "pick"), ("닫기", "")), ""), (three, "")):
                ask = dialogs.MessageDialog(None, "알림", "글", buttons, detail=detail)
                ask.show()
                guikit.pump()
                self.addCleanup(ask.close)
                self.assertLessEqual(ask.width(), 560)
                self.assertGreaterEqual(ask.height(), ask.layout().totalHeightForWidth(ask.width()), step)
                for button in ask.buttons.values():
                    self.assertTrue(button.isVisible())
                    self.assertGreaterEqual(button.width(), button.sizeHint().width(), "%s: %s" % (step, button.text()))
                    self.assertLessEqual(button.geometry().right(), ask.width() - 32)
                    self.assertEqual(button.font().pixelSize(), theme.TYPE["label"][0], step)
        theme.set_text("normal")
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
