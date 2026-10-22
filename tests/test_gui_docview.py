# -*- coding: utf-8 -*-
"""지문·힌트·해설 칸(gui/docview.py): 글·그림 조각 나누기, 언어별 코드 블록, 코드 조각 색칠, 없는 그림 안내, 어두운 테마, 확대,
글자 크기 단계마다 그려진 본문 크기와 줄 사이, 둥근 코드 상자, 조각 맨 위 여백, 머리·꼬리 위젯, 카드 안 칸(flat), 표 열 폭,
그림 재생기의 단계 이동, 줄어 보이는 그림의 [크게 보기]와 그림 창. PyQt6 가 없으면 전부 건너뜀."""
import base64
import os
import re
import shutil
import sys
import tempfile
import unittest

os.environ.setdefault("STUDY_NODE_PROBE", "0")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests import guikit  # noqa: E402

from PyQt6 import sip  # noqa: E402
from PyQt6.QtCore import QPoint, Qt  # noqa: E402
from PyQt6.QtGui import QColor, QPixmap, QRegion, qGray  # noqa: E402
from PyQt6.QtTest import QTest  # noqa: E402
from PyQt6.QtWidgets import QLabel, QPushButton, QWidget  # noqa: E402

import mdlite  # noqa: E402
from gui import kit, motion, theme  # noqa: E402
from gui import docview  # noqa: E402
from gui.docview import TIGHT_CSS, CodeView, DocView, FigureView, TextPiece, cell_text  # noqa: E402
from gui.widgets import Para  # noqa: E402

# 80×40 짜리 3장 GIF(장마다 100ms). n 번 장은 남색 바탕에 x = 4 + 24n ~ 20 + 24n, y = 10 ~ 30 에 초록 네모가 있음
GIF = base64.b64decode(
    "R0lGODlhUAAoAIEAAH/BjiU3RwAAAAAAACH/C05FVFNDQVBFMi4wAwEAAAAh+QQECgAAACwAAAAAUAAoAAAIkwADCBxIsKDBgwgTKlzIsKHDhxAjSpxIsaLFixgzatzI"
    "saPHjyBDihxJsqTJkxgBqFzJsqVKlBddymQJ0+LMmzUr3pyZk+JOmT0n/nQZVOLQlkUjHqWZ9OHSlU2dPgUQ1eFUqlUZXs2qdSrXhVu/Jgwr9iDZsgXPoh2odm2Atmvh"
    "opXrtq7du3jz6t3Lt6/fvwkDAgAh+QQFCgACACwAAAAAUAAoAIF/wY4gMUAAAAAAAAAIkwADCBxIsKDBgwgTKlzIsKHDhxAjSpxIsaLFixgzatzIsaPHjyBDihxJsqTJ"
    "kygRAljJsqXLlSktvpzZMmZFmjhtUsRJU+dEnjN9SgT6UmhEoi6NQkRaU6lDpiydPoUKQGpDqlWtLsSqdSvVrgq5glX5dexBsWYLok07cC3bAG7Zxk07963du3jz6t3L"
    "t6/fvzoDAgAh+QQFCgACACwAAAAAUAAoAIF/wY46UWYAAAAAAAAIkgADCBxIsKDBgwgTKlzIsKHDhxAjSpxIsaLFixgzatzIsaPHjyBDihxJsqTJkyhBAljJsqXLlSkt"
    "vpzZMmZFmjhtUsRJU+dEnjN9SgT6UmhEoi6NQkRaU6lDpiydPoUKQGpDqlWtLsSqdSvVrgq5gkUodqzBsmYJok0rcC1bt2nhmpXLtq7du3jz6t3Lt69fjwEBADs=")
# 200×20 짜리 남색 PNG
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAMgAAAAUAQMAAADyauCJAAAAA1BMVEUlN0fhQ83WAAAAD0lEQVR42mNgGAWjgIEBAAIIAAFQMUmAAAAAAElFTkSuQmCC")
GREEN = QColor("#7fc18e")

DOC = """## 관찰

첫 문단입니다.

![그림 1-1a. 장부 줄이 모이는 모습](assets/1-1a.gif)

## 풀이

끝 문단입니다.
"""

FUNCTION = """## 함수
```python
def solution(records, k):
```
```javascript
function solution(records, k) {}
```
```
둘 다 보이는 블록
```

- 목록 안의 조각

  ```js
  let inList = 1;
  ```
  ```py
  in_list = 1
  ```
"""

EVERYTHING = """# 제목

본문 문단과 `인라인 코드`, **굵게**.

| records | k | result |
|---|---|---|
| ["salt 3"] | 1 | ["salt"] |

> 인용 안의 안내입니다.

```python
def solution(records, k):
    return records[:k]
```

![그림](assets/1-1a.gif)

1. 첫째
2. 둘째
"""


def bright_share(widget):
    """tests/test_gui.py 의 bright_share 와 같은 셈. 찍은 그림을 8분의 1로 줄여 밝은 칸이 가로로 6칸 넘게 이어진 곳의 비율."""
    image = widget.grab().toImage()
    step = int(8 * image.devicePixelRatio())
    small = image.scaled(image.width() // step, image.height() // step, Qt.AspectRatioMode.IgnoreAspectRatio,
                         Qt.TransformationMode.SmoothTransformation)
    found = 0
    for y in range(small.height()):
        row = "".join("1" if qGray(small.pixel(x, y)) > 215 else "0" for x in range(small.width()))
        found += sum(len(run) for run in re.findall("1{6,}", row))
    return found / (small.width() * small.height())


def write(folder, name, data):
    path = os.path.join(folder, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(data)
    return path


def green_at(figure, frame):
    """지금 보이는 장에서 frame 번 장의 초록 네모 자리가 초록인지."""
    return figure.source.toImage().pixelColor(12 + 24 * frame, 20) == GREEN


class DocViewTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp()
        write(self.folder, "assets/1-1a.gif", GIF)
        self.view = DocView()
        self.view.resize(640, 700)
        self.view.show()

    def tearDown(self):
        self.view.close()
        self.view.deleteLater()
        guikit.pump()
        shutil.rmtree(self.folder)

    def shown(self, text, lang="python"):
        self.view.set_markdown(text, self.folder, lang)
        guikit.pump()
        return self.view.pieces

    def test_text_figure_text_makes_three_pieces(self):
        pieces = self.shown(DOC)
        self.assertEqual([type(piece) for piece in pieces], [TextPiece, FigureView, TextPiece])
        self.assertIn("첫 문단입니다.", pieces[0].toPlainText())
        self.assertNotIn("1-1a", pieces[0].toPlainText())
        self.assertIn("끝 문단입니다.", pieces[2].toPlainText())
        self.assertEqual(pieces[1].caption.text(), "그림 1-1a. 장부 줄이 모이는 모습")
        self.assertFalse(pieces[1].picture.pixmap().isNull())
        self.assertLess(pieces[0].geometry().bottom(), pieces[1].geometry().top())
        self.assertLess(pieces[1].geometry().bottom(), pieces[2].geometry().top())
        self.assertEqual(len(self.shown("다른 글")), 1)  # 내용을 바꾸면 앞의 조각은 빠짐

    def test_text_piece_grows_to_its_content(self):
        piece = self.shown("\n\n".join("문단 %d 입니다." % n for n in range(30)))[0]
        self.assertEqual(piece.verticalScrollBar().maximum(), 0)
        self.assertGreater(piece.height(), 30 * piece.fontMetrics().height())
        self.assertGreater(self.view.verticalScrollBar().maximum(), 0)  # 칸보다 길면 바깥에서 스크롤함

    def test_reloaded_pieces_do_not_scroll_inside(self):
        """이미 자리 잡은 칸에 다시 넣은 글 조각(언어 바꾸기, 같은 탭의 다음 문제)도 안에서 스크롤할 범위가 없어서 키로 움직여도 첫 줄이 밀리지 않음."""
        self.view.resize(400, 700)
        guikit.pump()
        for repeat in (5, 6, 8):  # 남는 스크롤 범위가 생기는지는 글 높이에 따라 달라서 길이를 셋으로 봄
            text = "\n\n".join("문단 %d. " % n + "칸 폭을 넘어 여러 줄로 접히는 문장입니다. " * repeat for n in range(8))
            for lang in ("python", "javascript"):
                piece = self.shown(text, lang)[0]
                self.assertEqual(piece.verticalScrollBar().maximum(), 0, (repeat, lang))
                QTest.keyClick(piece, Qt.Key.Key_Down)
                QTest.keyClick(piece, Qt.Key.Key_PageDown)
                self.assertEqual(piece.verticalScrollBar().value(), 0, (repeat, lang))

    def test_code_blocks_follow_the_language(self):
        python = self.shown(FUNCTION, "python")[0].toPlainText()
        for text in ("def solution(records, k):", "둘 다 보이는 블록", "in_list = 1"):
            self.assertIn(text, python)
        for text in ("function solution", "let inList"):
            self.assertNotIn(text, python)
        javascript = self.shown(FUNCTION, "javascript")[0].toPlainText()
        for text in ("function solution(records, k) {}", "둘 다 보이는 블록", "let inList = 1;"):
            self.assertIn(text, javascript)
        for text in ("def solution", "in_list"):
            self.assertNotIn(text, javascript)

    def test_code_piece_is_colored_and_shows_every_line(self):
        self.view.add_code("기준 풀이 (Python)", "def solution(records, k):\n    return len(records)\n", "python")
        code = self.view.add_code("기준 풀이 (JavaScript)", "function solution(records, k) {\n    const n = records.length;\n"
                                  "    return this.x + n + '%s';\n}" % ("긴 줄 " * 60), "javascript")
        guikit.pump()
        title, python, _, javascript = self.view.pieces
        self.assertIsInstance(title, TextPiece)
        self.assertEqual(title.toPlainText().strip(), "기준 풀이 (Python)")
        self.assertIs(code, javascript)
        self.assertIsInstance(python, CodeView)
        self.assertTrue(python.isReadOnly())
        self.assertIn(("def", "keyword"), guikit.painted(python, 0))
        self.assertIn(("solution", "def"), guikit.painted(python, 0))
        self.assertIn(("len", "builtin"), guikit.painted(python, 1))
        self.assertIn(("function", "keyword"), guikit.painted(javascript, 0))
        self.assertIn(("const", "keyword"), guikit.painted(javascript, 1))
        self.assertIn(("this", "self"), guikit.painted(javascript, 2))
        for view in (python, javascript):  # 모든 줄이 보이고 세로로 스크롤할 것이 없음
            self.assertEqual(view.verticalScrollBar().maximum(), 0)
        self.assertGreater(javascript.horizontalScrollBar().maximum(), 0)
        QTest.keyClicks(python, "x")  # 읽기 전용이라 글자가 들어가지 않고, 끝 줄바꿈으로 빈 줄이 생기지 않음
        self.assertEqual(python.toPlainText(), "def solution(records, k):\n    return len(records)")

    def test_missing_figure_shows_a_notice(self):
        """없는 그림 자리는 caption 글 한 줄이고 경로는 도움말에 있음."""
        pieces = self.shown("앞 글\n\n![없는 그림](assets/none.gif)\n")
        self.assertEqual(len(pieces), 2)
        self.assertIsInstance(pieces[1], Para)
        self.assertEqual((pieces[1].text(), pieces[1].toolTip()), ("그림을 불러오지 못했습니다.", "assets/none.gif"))
        self.assertEqual((pieces[1].property("role"), pieces[1].property("tone")), ("caption", "secondary"))
        self.assertEqual(pieces[1].font().pixelSize(), theme.TYPE["caption"][0])
        os.makedirs(os.path.join(self.folder, "assets", "folder.gif"))  # 있지만 열 수 없는 자리. 읽기 권한이 없는 파일처럼 OSError 가 남
        pieces = self.shown("![폴더](assets/folder.gif)")
        self.assertIsInstance(pieces[0], Para)
        self.assertEqual((pieces[0].text(), pieces[0].toolTip()), ("그림을 불러오지 못했습니다.", "assets/folder.gif"))

    def test_narrow_column_keeps_text_inside(self):
        """GIF 단추 줄보다 좁은 칸에서도 바탕이 칸보다 넓어지지 않아 글이 오른쪽 밖으로 밀리지 않음."""
        self.view.resize(160, 400)
        pieces = self.shown("긴 문단 " * 40 + "\n\n" + DOC)
        self.assertLessEqual(self.view.widget().width(), self.view.viewport().width())
        self.assertLessEqual(pieces[0].width(), self.view.viewport().width())

    def test_png_figure_has_no_step_bar_and_half_size(self):
        write(self.folder, "assets/1-1b.png", PNG)
        figure = self.shown("![표](assets/1-1b.png)")[0]
        self.assertIsNone(figure.movie)
        self.assertEqual(figure.picture.pixmap().deviceIndependentSize().width(), 100)
        self.assertIsNone(figure.controls)
        figure.hide()  # 움직이는 그림이 없어도 가릴 수 있음

    def test_add_table_and_linked_paragraph(self):
        self.view.add_table(["번호", "쓰는 기술"], [["1-2", "`dict` 집계"], ["1-3", "**두 포인터**"]])
        self.view.add_para("더 풀어 볼 문제", "h2")
        self.view.add_para("백준 1234 예시 문제", link="https://www.acmicpc.net/problem/1234")
        guikit.pump()
        table, title, link = self.view.pieces
        self.assertIn("dict 집계", table.toPlainText())
        self.assertIn('class="h2"', title.markup)
        got = []
        self.view.linked.connect(got.append)
        QTest.mouseClick(link.viewport(), guikit.LEFT, pos=QPoint(10, link.height() // 2))
        self.assertEqual(got, ["https://www.acmicpc.net/problem/1234"])

    def test_zoom_changes_css_font_size_and_keeps_place(self):
        pieces = self.shown(EVERYTHING * 3)
        self.view.add_code("기준 풀이 (Python)", "x = 1", "python")
        guikit.pump()
        text, code = pieces[0], self.view.pieces[-1]
        self.assertIn("font-size: %dpx" % (14 + theme.DOC_PX), text.document().defaultStyleSheet())
        self.view.restyle(theme.doc_css(), theme.code_font())  # 기본 CSS 는 새 문서 규칙이라 확대 0 의 본문 CSS 에서 잼
        guikit.pump()
        before, size = text.height(), theme.CODE_PX
        bar = self.view.verticalScrollBar()
        self.assertGreater(bar.maximum(), 0)
        bar.setValue(bar.maximum() // 2)
        place = bar.value()
        self.view.restyle(theme.doc_css(4), theme.code_font(4))
        guikit.pump()
        self.assertIn("font-size: %dpx" % (14 + theme.DOC_PX + 4), text.document().defaultStyleSheet())
        self.assertGreater(text.height(), before)
        self.assertEqual(code.font().pixelSize(), size + 4)
        self.assertEqual(bar.value(), place)

    def test_dark_theme_has_no_bright_area(self):
        mode = theme.state["mode"]
        self.addCleanup(theme.set_mode, mode)
        theme.set_mode("dark")
        self.view.restyle(theme.doc_css(), theme.code_font())
        self.shown(EVERYTHING)
        self.view.add_table(["번호", "쓰는 기술"], [["1-2", "집계"]])
        self.view.add_code("기준 풀이 (Python)", "def solution(records, k):\n    return records[:k]", "python")
        self.view.resize(640, 1400)
        guikit.pump(60)
        self.assertEqual(bright_share(self.view), 0)

    def test_defaults_use_the_spacing_tokens(self):
        """기본 안쪽 여백 24, 조각 사이 16(문단 사이와 같음). 좁은 칸의 표·코드 상자 여백도 8·12 단위."""
        margins = self.view.box.contentsMargins()
        self.assertEqual((margins.left(), margins.top(), margins.right(), margins.bottom(), self.view.box.spacing()), (24, 24, 24, 24, 16))
        pieces = self.shown(DOC)
        self.assertEqual(pieces[1].y() - pieces[0].geometry().bottom() - 1, 16)
        for value in re.findall(r"padding: ([^;]+);", TIGHT_CSS):
            for number in re.findall(r"\d+", value):
                self.assertIn(int(number), theme.SPACE)

    def test_piece_starts_without_a_top_margin(self):
        """조각 맨 위의 절 제목과 코드 상자는 위 여백 없이 조각 첫 줄에 붙음. 칸 위 간격은 안쪽 여백 24 가 줌."""
        piece = self.shown("## 관찰\n\n첫 문단입니다.\n\n## 풀이\n\n끝 문단입니다.")[0]
        first = piece.document().begin()
        self.assertEqual(first.text(), "관찰")
        self.assertEqual(first.blockFormat().topMargin(), 0)
        later = [block for block in blocks(piece) if block.text() == "풀이"][0]
        self.assertEqual(later.blockFormat().topMargin(), 24)  # 조각 안의 절 제목은 CSS 의 위 24 를 받음
        piece = self.shown("```python\nx = 1\n```\n\n뒤 문단입니다.")[0]
        self.assertEqual(piece.code_boxes()[0].top(), 0)

    def test_code_box_is_round_and_filled_without_a_border(self):
        """코드 상자는 테두리 없이 surface_alt 로 채운 모서리 12 상자. 모서리 안쪽 1px 은 바탕색(둥긂)이고 위 변 가운데는 상자 색."""
        self.addCleanup(theme.set_mode, theme.state["mode"])
        for scheme in ("light", "dark"):
            theme.set_mode(scheme)
            self.view.restyle(theme.journey_css(), theme.code_font(theme.text_px() - 1))
            piece = self.shown("앞 문단입니다.\n\n```python\nx = 1\ny = 2\n```\n\n뒤 문단입니다.")[0]
            guikit.pump(30)
            image = self.view.grab().toImage()
            box = piece.code_boxes()[0].translated(piece.mapTo(self.view, QPoint(0, 0)).toPointF())
            left, top, right = round(box.left()), round(box.top()), round(box.right()) - 1
            self.assertEqual(image.pixelColor(left + 1, top + 1).name(), theme.color("surface"), scheme)
            self.assertEqual(image.pixelColor(right - 1, top + 1).name(), theme.color("surface"), scheme)
            self.assertEqual(image.pixelColor(round(box.center().x()), top).name(), theme.color("surface_alt"), scheme)
            self.assertEqual(image.pixelColor(left, round(box.center().y())).name(), theme.color("surface_alt"), scheme)

    def test_code_box_has_the_same_space_above_and_below(self):
        """코드 상자 위아래로 보이는 간격(앞 문단 글 끝에서 상자 위, 상자 아래에서 뒤 문단 글 위)이 세 글자 단계에서 2px 안으로 같음."""
        self.addCleanup(theme.set_text, "normal")
        for step in theme.TEXT_STEPS:
            theme.set_text(step)
            self.view.restyle(theme.journey_css(), theme.code_font(theme.text_px() - 1))
            piece = self.shown("앞 문단입니다.\n\n```python\nx = 1\n```\n\n뒤 문단입니다.")[0]
            guikit.pump(30)
            rows = ink_rows(self.view.grab().toImage(), theme.color("surface"), theme.color("surface_alt"))
            box = piece.code_boxes()[0].translated(piece.mapTo(self.view, QPoint(0, 0)).toPointF())
            above = round(box.top()) - max(y for y in rows if y < box.top()) - 1
            below = min(y for y in rows if y > box.bottom()) - round(box.bottom()) - 1
            self.assertLessEqual(abs(above - below), 2, (step, above, below))
            self.assertGreaterEqual(min(above, below), 16, step)

    def test_head_and_tail_stay_outside_the_pieces(self):
        """set_head 위젯은 조각 위, set_tail 위젯은 조각 아래에 있고 set_markdown·clear 가 지우지 않음. 새로 주면 앞 위젯은 숨음."""
        head, tail = kit.label("머리", "caption"), kit.label("꼬리", "caption")
        self.view.set_head(head)
        self.view.set_tail(tail)
        pieces = self.shown(DOC)
        self.assertNotIn(head, pieces)
        self.assertLess(head.geometry().bottom(), pieces[0].y())
        self.assertGreater(tail.y(), pieces[-1].geometry().bottom())
        self.view.add_para("더한 문단")
        guikit.pump()
        self.assertGreater(tail.y(), self.view.pieces[-1].geometry().bottom())  # 뒤에 더한 조각도 꼬리 위에 들어감
        self.shown("다른 글")
        self.assertTrue(head.isVisible() and tail.isVisible())
        other = kit.label("새 머리", "caption")
        self.view.set_head(other)
        guikit.pump()
        self.assertFalse(head.isVisible())
        self.assertTrue(other.isVisible())
        self.view.set_tail(None)
        guikit.pump()
        self.assertFalse(tail.isVisible())

    def test_flat_view_does_not_paint_its_sheet(self):
        """flat 칸은 flat 속성을 달고 바탕을 칠하지 않아 카드의 면이 보임. 기본 칸은 surface 로 칠함."""
        for flat, expected in ((False, theme.color("surface")), (True, "#ff00ff")):
            view = DocView(flat=flat)
            self.addCleanup(view.deleteLater)
            self.assertEqual(bool(view.property("flat")), flat)
            view.resize(200, 100)
            view.sheet.resize(200, 100)
            canvas = QPixmap(200, 100)
            canvas.fill(QColor("#ff00ff"))
            view.sheet.render(canvas, QPoint(0, 0), QRegion(), QWidget.RenderFlag.DrawChildren)  # 창 바탕 없이 칠한 것만
            self.assertEqual(canvas.toImage().pixelColor(100, 50).name(), expected, flat)

    def test_short_table_column_keeps_its_words_whole(self):
        """보스 표처럼 한 열이 짧아도 그 열은 띄어쓰기 없는 가장 긴 덩어리와 칸 여백이 들어가는 폭을 받아 낱말 안에서 줄을 바꾸지 않음."""
        work = "장부 줄을 상품 이름으로 묶어 개수를 세고 많이 팔린 순서로 정렬한 뒤 앞에서 k개를 고르는 일을 한 칸에 길게 씁니다"
        for width in (468, 640):
            self.view.resize(width, 700)
            self.view.clear()
            self.view.add_table(["이 보스에서 하는 일", "익힌 문제"], [[work, "1-1"], ["짧은 일", "1-3"]])
            guikit.pump(30)
            piece = self.view.pieces[0]
            table = piece.grid_tables()[0]
            head = table.cellAt(0, 1).firstCursorPosition().block()
            self.assertEqual(cell_text(table.cellAt(0, 1)), "익힌 문제")
            self.assertLessEqual(head.layout().lineCount(), 2, width)  # 낱말 둘이라 줄이 바뀌어도 둘까지
            for number in range(head.layout().lineCount()):
                line = head.layout().lineAt(number)
                self.assertIn(head.text()[line.textStart():line.textStart() + line.textLength()].strip(), ("익힌", "문제", "익힌 문제"), width)


class FigureViewTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.path = write(self.folder, "assets/1-1a.gif", GIF)

    def tearDown(self):
        guikit.pump()
        shutil.rmtree(self.folder)

    def figure(self):
        figure = FigureView(self.path, "그림 1-1a. 장부 줄이 모이는 모습")
        figure.resize(400, 200)
        figure.show()
        self.addCleanup(figure.deleteLater)
        self.addCleanup(figure.close)
        guikit.pump()
        return figure

    def test_buttons_step_through_frames(self):
        figure = self.figure()
        self.assertEqual(figure.counter.text(), "1 / 3")
        self.assertTrue(green_at(figure, 0))
        self.assertFalse(figure.first_btn.isEnabled() or figure.prev_btn.isEnabled())
        guikit.click(figure.next_btn)
        self.assertEqual(figure.counter.text(), "2 / 3")
        self.assertTrue(green_at(figure, 1))
        guikit.click(figure.next_btn)
        self.assertEqual(figure.counter.text(), "3 / 3")
        self.assertFalse(figure.next_btn.isEnabled())
        guikit.click(figure.prev_btn)
        self.assertEqual(figure.counter.text(), "2 / 3")
        self.assertTrue(green_at(figure, 1))
        guikit.click(figure.first_btn)
        self.assertEqual(figure.counter.text(), "1 / 3")
        self.assertTrue(green_at(figure, 0))
        self.assertEqual(figure.caption.text(), "그림 1-1a. 장부 줄이 모이는 모습")

    def test_shown_at_half_size_and_shrinks_with_the_column(self):
        self.assertEqual(self.figure().picture.pixmap().deviceIndependentSize().width(), 40)
        self.path = write(self.folder, "assets/1-1b.png", PNG)
        figure = self.figure()
        self.assertEqual(figure.picture.pixmap().deviceIndependentSize().width(), 100)
        figure.resize(60, 200)
        guikit.pump()
        self.assertEqual(figure.width(), 60)
        self.assertLessEqual(figure.picture.pixmap().deviceIndependentSize().width(), 60)

    def test_shrunk_figure_opens_at_its_drawn_size_when_clicked(self):
        self.path = write(self.folder, "assets/1-1b.png", PNG)
        figure = self.figure()
        self.assertFalse(figure.shrunk)
        QTest.mouseClick(figure.picture, guikit.LEFT)
        guikit.pump()
        self.assertIsNone(figure.dialog, "다 보이는 그림은 눌러도 창을 띄우지 않음")
        self.assertFalse(figure.zoom_btn.isVisible())
        figure.resize(60, 200)
        guikit.pump()
        self.assertTrue(figure.shrunk)
        self.assertEqual("", figure.picture.toolTip())
        self.assertTrue(figure.zoom_btn.isVisible())  # 줄어 보일 때만 [크게 보기]가 그림 아래 오른쪽에 보임
        self.assertGreater(figure.zoom_row.y(), figure.picture.geometry().bottom())
        self.assertEqual((figure.zoom_btn.text(), figure.zoom_btn.objectName(), figure.zoom_btn.property("scale")), ("크게 보기", "text", "s"))
        QTest.mouseClick(figure.picture, guikit.LEFT)
        guikit.pump()
        dialog = figure.dialog
        self.assertTrue(dialog.isVisible())
        self.assertEqual("그림 1-1a. 장부 줄이 모이는 모습", dialog.windowTitle())
        self.assertEqual(100, dialog.picture.pixmap().deviceIndependentSize().width())
        self.assertEqual(dialog.property("ui"), "2")
        title = [label.text() for label in dialog.findChildren(QLabel) if label.property("role") == "headline"]
        self.assertEqual(title, ["그림 1-1a. 장부 줄이 모이는 모습"])
        close = [button for button in dialog.findChildren(QPushButton) if button.text() == "닫기"]
        self.assertEqual([(button.objectName(), button.property("scale")) for button in close], [("", "l")])
        dialog.close()
        guikit.pump()
        guikit.click(figure.zoom_btn)  # [크게 보기]를 눌러도 같은 창이 뜸
        guikit.pump()
        second = figure.dialog
        self.addCleanup(lambda: sip.isdeleted(second) or second.close())
        self.assertTrue(second.isVisible())

    def test_moving_figure_keeps_its_buttons_in_the_dialog(self):
        """움직이는 그림의 넘김 단추는 kit 글자 단추 s 이고, 줄어 보일 때 [크게 보기]는 넘김 줄에 자리가 있으면 그 오른쪽 끝에, 없으면
        그림 아래 줄에 있어 글자가 잘리지 않음. 그림 창은 누른 때의 장과 넘김 단추를 가지고 저절로 재생하지 않음."""
        self.addCleanup(setattr, docview, "SCALE", docview.SCALE)
        docview.SCALE = 0.125  # 80 폭 시험 그림을 640 폭으로 그려 넘김 줄이 들어가는 폭에서도 줄어 보이게 함
        figure = kit.page(FigureView(self.path))
        figure.resize(700, 400)
        figure.show()
        self.addCleanup(figure.deleteLater)
        self.addCleanup(figure.close)
        guikit.pump()
        for button in (figure.first_btn, figure.prev_btn, figure.play_btn, figure.next_btn):
            self.assertEqual((button.objectName(), button.property("scale")), ("text", "s"))
        self.assertEqual(figure.counter.property("role"), "caption")
        self.assertFalse(figure.shrunk or figure.zoom_btn.isVisible() or figure.zoom_row.isVisible())
        guikit.click(figure.next_btn)
        figure.resize(600, 400)
        guikit.pump()
        self.assertTrue(figure.shrunk and figure.zoom_btn.isVisible())
        self.assertIs(figure.zoom_btn.parentWidget(), figure.controls)  # 넘김 줄 오른쪽 끝
        self.assertFalse(figure.zoom_row.isVisible())
        self.assertLessEqual(figure.zoom_btn.geometry().right(), figure.width())
        self.assertGreater(figure.zoom_btn.x(), figure.counter.geometry().right())
        narrow = figure.controls.sizeHint().width() - 10
        figure.resize(narrow, 400)
        guikit.pump()
        self.assertIs(figure.zoom_btn.parentWidget(), figure.zoom_row)  # 넘김 줄에 자리가 없으면 그림 아래 줄로 내려감
        self.assertTrue(figure.zoom_row.isVisible() and figure.zoom_btn.isVisible())
        self.assertGreater(figure.zoom_row.y(), figure.controls.geometry().bottom())
        self.assertGreaterEqual(figure.zoom_btn.width(), figure.zoom_btn.sizeHint().width())
        guikit.click(figure.zoom_btn)
        dialog = figure.dialog
        self.addCleanup(lambda: sip.isdeleted(dialog) or dialog.close())
        self.assertEqual(dialog.view.counter.text(), "2 / 3")
        self.assertFalse(dialog.view.zoom_btn.isVisible() or dialog.view.playing)
        self.assertGreaterEqual(dialog.width(), min(dialog.view.controls.sizeHint().width() + 48, dialog.screen().availableGeometry().width() - 40))

    def test_does_not_play_when_motion_is_off(self):
        self.assertFalse(motion.enabled)
        figure = self.figure()
        guikit.pump(400)  # 세 장을 다 넘기고도 남는 시간
        self.assertEqual(figure.counter.text(), "1 / 3")
        self.assertFalse(figure.playing or figure.timer.isActive())
        self.assertEqual(figure.play_btn.text(), "재생")

    def test_plays_once_and_stops_on_the_last_frame(self):
        motion.enabled = True
        self.addCleanup(setattr, motion, "enabled", False)
        figure = self.figure()
        guikit.wait_until(lambda: not figure.playing, timeout=10)
        self.assertEqual(figure.counter.text(), "3 / 3")
        self.assertTrue(green_at(figure, 2))
        self.assertEqual(figure.play_btn.text(), "재생")
        guikit.click(figure.play_btn)  # 마지막 장에서 누르면 처음부터 다시 재생함
        self.assertTrue(figure.playing)
        self.assertEqual(figure.counter.text(), "1 / 3")
        self.assertEqual(figure.play_btn.text(), "멈춤")
        figure.hide()  # 가려지면 멈춤
        self.assertFalse(figure.playing or figure.timer.isActive())

    def test_file_can_be_renamed_and_removed_while_shown(self):
        figure = self.figure()
        moved = self.path + ".old"
        os.rename(self.path, moved)
        os.remove(moved)
        guikit.click(figure.next_btn)
        guikit.click(figure.next_btn)
        guikit.click(figure.prev_btn)  # 뒤로 가려면 0번 장부터 다시 읽음. 파일이 아니라 메모리에서 읽어야 됨
        self.assertEqual(figure.counter.text(), "2 / 3")
        self.assertTrue(green_at(figure, 1))
        guikit.click(figure.first_btn)
        self.assertTrue(green_at(figure, 0))


def size(block):
    """블록 첫 글 조각의 글자 px."""
    return block.begin().fragment().charFormat().font().pixelSize()


def blocks(piece):
    out, block = [], piece.document().begin()
    while block.isValid():
        out.append(block)
        block = block.next()
    return out


def ink_rows(image, back, box):
    """글자 화소가 있는 줄(y)들. 바탕색과 코드 상자 색이 아닌 어두운 화소가 있는 줄을 셈."""
    back, box = qGray(QColor(back).rgb()), qGray(QColor(box).rgb())
    rows = set()
    for y in range(image.height()):
        for x in range(30, image.width() - 30):
            gray = qGray(image.pixel(x, y))
            if abs(gray - back) > 60 and abs(gray - box) > 60:
                rows.add(y)
                break
    return rows


class TextStepTest(unittest.TestCase):
    """새 문서 규칙(theme.journey_css 는 web_css 와 같음)으로 그린 글의 크기와 줄 사이가 글자 크기 단계를 따름.
    CSS 글이 아니라 그려진 블록의 글자 크기와 줄 자리를 봄."""

    def setUp(self):
        self.addCleanup(theme.set_text, "normal")

    def drawn(self):
        view = DocView()
        self.addCleanup(view.deleteLater)
        self.addCleanup(view.close)
        view.resize(640, 900)
        view.restyle(theme.journey_css(), theme.code_font(theme.text_px() - 1))
        view.show()
        view.set_markdown("# 문서 제목\n\n" + "두 줄을 넘는 문단입니다. " * 12 + "\n\n```python\nx = 1\n```\n", "", "python")
        code = view.add_code("기준 풀이 (Python)", "def solution():\n    return 1", "python")
        guikit.pump(30)
        found = {}
        for block in blocks(view.pieces[0]):
            if block.text().strip():
                found.setdefault(block.text()[:4], block)
        return found, code

    def test_body_heading_and_code_follow_the_text_step(self):
        expected = {"normal": (17, 28, 22, 15), "large": (19, 32, 24, 17), "larger": (21, 36, 26, 19)}
        for step in theme.TEXT_STEPS:
            theme.set_text(step)
            found, code = self.drawn()
            body = found["두 줄을"]
            layout = body.layout()
            self.assertGreaterEqual(layout.lineCount(), 2, step)
            got = (size(body), round(layout.lineAt(1).y() - layout.lineAt(0).y()), size(found["문서 제"]), size(found["x = "]))
            self.assertEqual(got, expected[step], step)
            self.assertEqual(got, (theme.TYPE["body"][0], theme.TYPE["body"][1], theme.TYPE["headline"][0], theme.TYPE["code"][0]), step)
            self.assertEqual(code.font().pixelSize(), theme.TYPE["code"][0], step)  # 기준 풀이도 문서 코드와 같은 크기

    def test_default_code_font_is_the_code_step(self):
        """DocView 의 기본 코드 글꼴(기준 풀이)은 code 크기: 보통 15, 크게 17."""
        for step, size in (("normal", 15), ("large", 17)):
            theme.set_text(step)
            view = DocView()
            self.addCleanup(view.deleteLater)
            self.assertEqual(view.add_code("", "x = 1", "python").font().pixelSize(), size, step)

    def test_result_css_keeps_lines_close(self):
        """결과 칸 CSS 는 새 문서 규칙에서 문단 아래만 4 로 줄임. 글자 크기와 줄 높이는 같음."""
        markup = mdlite.to_html("테스트 1 〉 통과\n\n테스트 2 〉 실패")
        normal, result = TextPiece(markup, theme.journey_css()), TextPiece(markup, theme.result_css())
        self.addCleanup(normal.deleteLater)
        self.addCleanup(result.deleteLater)
        first = normal.document().begin(), result.document().begin()
        self.assertEqual([block.blockFormat().bottomMargin() for block in first], [16, 4])
        self.assertEqual([size(block) for block in first], [theme.TYPE["body"][0]] * 2)
        self.assertTrue(theme.result_css().startswith(theme.web_css()))


if __name__ == "__main__":
    unittest.main()
