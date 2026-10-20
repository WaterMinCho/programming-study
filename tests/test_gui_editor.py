# -*- coding: utf-8 -*-
"""편집기 모듈(gui/editor.py)의 언어 프로필: 자바스크립트 색칠·줄 주석·들여쓰기·괄호 닫기, 언어 전환, 붙여넣기 옵션.
파이썬 쪽 동작과 줄 번호·찾기 막대는 tests/test_gui.py 가 그대로 봄. PyQt6 가 없으면 전부 건너뜀."""
import os
import sys
import unittest

os.environ.setdefault("STUDY_NODE_PROBE", "0")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests import guikit  # noqa: E402

from PyQt6.QtCore import QMimeData, Qt  # noqa: E402
from PyQt6.QtGui import QGuiApplication, QKeySequence, QTextCursor  # noqa: E402
from PyQt6.QtTest import QTest  # noqa: E402

from gui import editor, theme, widgets  # noqa: E402
from gui.editor import JAVASCRIPT, LANGS, PYTHON, CodeEditor, scan  # noqa: E402

SLASH = (Qt.Key.Key_Slash, guikit.CTRL)


class EditorCase(unittest.TestCase):
    lang = JAVASCRIPT

    def setUp(self):
        self.ed = CodeEditor(lang=self.lang)
        self.ed.setFont(theme.code_font())

    def keys(self, *steps):
        for step in steps:
            if isinstance(step, str):
                QTest.keyClicks(self.ed, step)
            else:
                QTest.keyClick(self.ed, *(step if isinstance(step, tuple) else (step,)))
        return self.ed.toPlainText()

    def put(self, text):
        """| 를 뺀 글을 넣고 | 자리에 커서를 둠. | 가 둘이면 그 사이를 선택함."""
        parts = text.split("|")
        self.ed.setPlainText("".join(parts))
        cursor = self.ed.textCursor()
        cursor.setPosition(len(parts[0]))
        cursor.setPosition(len("".join(parts[:-1])), QTextCursor.MoveMode.KeepAnchor)
        self.ed.setTextCursor(cursor)

    def view(self):
        """커서와 선택 양 끝을 | 로 표시한 글."""
        text, cursor = self.ed.toPlainText(), self.ed.textCursor()
        for spot in sorted({cursor.selectionStart(), cursor.selectionEnd()}, reverse=True):
            text = text[:spot] + "|" + text[spot:]
        return text

    def typed(self, start, *steps):
        self.put(start)
        self.keys(*steps)
        return self.view()

    def kinds(self, code):
        self.ed.setPlainText(code)
        return [guikit.painted(self.ed, line) for line in range(self.ed.blockCount())]

    def states(self):
        return [self.ed.document().findBlockByNumber(line).userState() for line in range(self.ed.blockCount())]


class LangTest(unittest.TestCase):
    def test_profiles_and_reexports(self):
        self.assertEqual(LANGS, {"python": PYTHON, "javascript": JAVASCRIPT})
        self.assertEqual((PYTHON.name, PYTHON.label, PYTHON.ext, PYTHON.comment), ("python", "Python", ".py", "#"))
        self.assertEqual((JAVASCRIPT.name, JAVASCRIPT.label, JAVASCRIPT.ext, JAVASCRIPT.comment), ("javascript", "JavaScript", ".js", "//"))
        self.assertEqual(JAVASCRIPT.pairs, dict(editor.PAIRS, **{"`": "`"}))
        self.assertEqual((PYTHON.quotes, JAVASCRIPT.quotes, JAVASCRIPT.openers), (('"', "'"), ('"', "'", "`"), editor.OPENERS))
        for name in ("BLANK", "BUILTINS", "DECORATOR", "INDENT", "KEYWORDS", "OPENERS", "PAIRS", "STRING_END", "STRING_PREFIX", "TOKEN", "TRIPLE",
                     "CodeEditor", "FindBar", "Highlighter", "LineNumbers", "PlainEdit", "carried", "line_at", "scan"):
            self.assertIs(getattr(widgets, name), getattr(editor, name), name)  # 기존 import 경로가 그대로 동작함

    def test_scan_knows_javascript_comments_and_template_strings(self):
        self.assertEqual(scan("a = 1 // x", lang=JAVASCRIPT), ("a = 1 ", "//"))
        self.assertEqual(scan("x /* y", lang=JAVASCRIPT), ("x ", "/*"))
        self.assertEqual(scan("z */ w", "/*", lang=JAVASCRIPT), (" w", ""))
        self.assertEqual(scan("a \\*/ b", "/*", lang=JAVASCRIPT), (" b", ""))  # 블록 주석 안의 역슬래시는 아무것도 가리지 않음
        self.assertEqual(scan("`a${b}` + c", lang=JAVASCRIPT), (" + c", ""))
        self.assertEqual(scan("`a${b", lang=JAVASCRIPT), ("", "`"))
        self.assertEqual(scan("c}` + 'x' + \"//\"", "`", lang=JAVASCRIPT), (" +  + ", ""))
        self.assertEqual(scan("s = 'x' # c", lang=PYTHON), ("s =  ", "#"))  # 파이썬은 지금과 같음
        self.assertEqual(scan("s = 'x' # c"), ("s =  ", "#"))
        self.assertEqual(scan('"""abc'), ("", '"""'))
        self.assertEqual(scan("x // y", lang=PYTHON), ("x // y", ""))  # 파이썬의 // 는 나눗셈


class JsHighlightTest(EditorCase):
    def test_each_kind_of_token_gets_its_own_color(self):
        code = ("const total = 10n + 0x1F + 2.5e3;\n"
                "function f(items) {\n"
                "    return console.log(this.size, Math.max(1, 2));\n"
                "}\n"
                "class Dog extends Animal {}\n"
                "let $el = $, undefined_x = null;  // 설명 if\n"
                "x = a / b // 나누기\n"
                "url = \"http://x\" + obj.default;\n")
        self.assertEqual(self.kinds(code), [
            [("const", "keyword"), ("10n", "number"), ("0x1F", "number"), ("2.5e3", "number")],
            [("function", "keyword"), ("f", "def")],
            [("return", "keyword"), ("console", "builtin"), ("this", "self"), ("Math", "builtin"), ("1", "number"), ("2", "number")],  # 점 뒤는 속성
            [],
            [("class", "keyword"), ("Dog", "def"), ("extends", "keyword")],
            [("let", "keyword"), ("null", "keyword"), ("// 설명 if", "comment")],  # $el 과 $ 는 여느 이름, undefined_x 는 예약어가 아님
            [("// 나누기", "comment")],
            [('"http://x"', "string"), ("default", "keyword")],  # 문자열 안의 // 는 주석이 아님
            []])
        self.assertEqual(self.states(), [0] * 9)

    def test_template_strings_and_block_comments_continue_on_the_next_line(self):
        code = ("const s = `a ${x} b\n"
                "c` + 1;\n"
                "/* 첫 줄 let\n"
                "둘째 줄 */ let y = 2;\n"
                "z = 3; /* 한 줄 */ w = 4;\n"
                "t = `x // y`; // z\n")
        self.assertEqual(self.kinds(code), [
            [("const", "keyword"), ("`a ${x} b", "string")],
            [("c`", "string"), ("1", "number")],
            [("/* 첫 줄 let", "comment")],
            [("둘째 줄 */", "comment"), ("let", "keyword"), ("2", "number")],
            [("3", "number"), ("/* 한 줄 */", "comment"), ("4", "number")],
            [("`x // y`", "string"), ("// z", "comment")],
            []])
        self.assertEqual(self.states(), [1, 0, 2, 0, 0, 0, 0])  # 1 은 템플릿 문자열, 2 는 블록 주석이 이어짐

    def test_decorator_and_hash_mean_nothing_in_javascript(self):
        self.assertEqual(self.kinds("@app.route\nx = 1 # 2"), [[], [("1", "number"), ("2", "number")]])


class JsEditTest(EditorCase):
    def test_ctrl_slash_toggles_double_slash_and_undoes_in_one_step(self):
        self.put("let x = 1;\nconsole.log(|x);")
        self.assertEqual(self.keys(SLASH), "let x = 1;\n// console.log(x);")
        self.assertEqual(self.keys(SLASH), "let x = 1;\nconsole.log(x);")
        self.put("function f() {\n|    a();\n\n        b();\n|    return 1;\n}")
        self.assertEqual(self.keys(SLASH), "function f() {\n    // a();\n\n    //     b();\n    return 1;\n}")  # 가장 얕은 들여쓰기 자리
        self.assertEqual(self.keys(SLASH), "function f() {\n    a();\n\n        b();\n    return 1;\n}")
        self.put("|// 설명\nx = 1;|")
        self.assertEqual(self.keys(SLASH), "// // 설명\n// x = 1;")  # 주석이 아닌 줄이 섞이면 모두 주석으로 만듦
        self.ed.undo()
        self.assertEqual(self.ed.toPlainText(), "// 설명\nx = 1;")  # 한 번에 되돌아감
        self.put("//x = 1;|")
        self.assertEqual(self.keys(SLASH), "x = 1;")  # 공백 없이 붙은 // 도 풂
        self.put("# x|")
        self.assertEqual(self.keys(SLASH), "// # x")  # 파이썬 주석 글자는 자바스크립트에서 주석이 아님

    def test_enter_indents_after_an_opening_bracket_and_splits_an_empty_pair(self):
        self.assertEqual(self.typed("if (x) {|", Qt.Key.Key_Return, "y();", Qt.Key.Key_Return), "if (x) {\n    y();\n    |")
        self.assertEqual(self.typed("const a = [|", Qt.Key.Key_Return), "const a = [\n    |")
        self.assertEqual(self.typed("f(|", Qt.Key.Key_Return), "f(\n    |")
        self.assertEqual(self.typed("f({|})", Qt.Key.Key_Return), "f({\n    |\n})")  # 빈 쌍 사이면 닫는 괄호를 다음 줄로 내림
        self.assertEqual(self.typed("    g([|])", Qt.Key.Key_Return), "    g([\n        |\n    ])")
        self.assertEqual(self.typed("s = '{';|", Qt.Key.Key_Return), "s = '{';\n|")  # 문자열 안의 괄호는 열지 않음
        self.assertEqual(self.typed("x = 1; // {|", Qt.Key.Key_Return), "x = 1; // {\n|")  # 주석 안의 괄호도 열지 않음
        self.assertEqual(self.typed("if (x) {  // 설명|", Qt.Key.Key_Return), "if (x) {  // 설명\n    |")
        self.assertEqual(self.typed("def f():|", Qt.Key.Key_Return), "def f():\n|")  # 콜론은 자바스크립트에서 블록을 열지 않음

    def test_closing_bracket_on_a_blank_indent_outdents_one_level(self):
        self.assertEqual(self.typed("if (x) {\n    |", "}"), "if (x) {\n}|")
        self.ed.undo()
        self.assertEqual(self.view(), "if (x) {\n    |")  # 내어쓰기와 괄호가 한 번에 되돌아감
        self.assertEqual(self.typed("a = [\n      |", "]"), "a = [\n    ]|")  # 4의 배수 자리까지만 지움
        self.assertEqual(self.typed("f(\n        |", ")"), "f(\n    )|")
        self.assertEqual(self.typed("    x|", "}"), "    x}|")  # 빈칸이 아닌 글자 뒤에서는 그대로 들어감
        self.assertEqual(self.typed("|", "}"), "}|")  # 빈 줄에서도 그대로
        self.assertEqual(self.typed("if (x) {\n    |}", "}"), "if (x) {\n}|")  # 이미 있는 닫는 괄호는 넘어감
        self.put("|")
        typed = self.keys("function f() {", Qt.Key.Key_Return, "return 1;", Qt.Key.Key_Return, Qt.Key.Key_Backspace)
        self.assertEqual(typed, "function f() {\n    return 1;\n\n}")  # 처음부터 치면 닫는 괄호는 자동으로 생김

    def test_backtick_closes_and_brackets_inside_strings_stay_plain(self):
        self.assertEqual(self.typed("x = |", "`"), "x = `|`")
        self.assertEqual(self.keys("("), "x = `(`")  # 문자열 안의 괄호는 닫지 않음
        self.assertEqual(self.typed("x = `(|`", "`"), "x = `(`|")  # 닫는 백틱은 넘어감
        self.assertEqual(self.typed("y = \"|\"", "("), 'y = "(|"')
        self.assertEqual(self.typed("z = |", "(", "[", "{"), "z = ([{|}])")
        self.assertEqual(self.typed("t = `a\n|", "("), "t = `a\n(|")  # 앞줄에서 이어진 템플릿 문자열 안
        self.assertEqual(self.typed("x = `${|}`", "("), "x = `${(|}`")  # ${} 도 문자열의 일부
        self.assertEqual(self.typed("name|", "`"), "name`|")  # 글자 바로 뒤의 따옴표는 닫지 않음(태그 템플릿)
        self.assertEqual(self.typed("/* |", "("), "/* (|")  # 주석 안
        self.assertEqual(self.typed("|", "`"), "`|`")  # 줄 맨 앞에서도 닫음
        self.assertEqual(self.keys("`"), "``")  # 닫는 백틱을 넘어감

    def test_backspace_between_an_empty_pair_removes_both(self):
        self.assertEqual(self.typed("x = `|`", Qt.Key.Key_Backspace), "x = |")
        self.assertEqual(self.typed("x = {|}", Qt.Key.Key_Backspace), "x = |")


class PythonElectricTest(EditorCase):
    lang = PYTHON

    def test_closing_bracket_on_a_blank_indent_stays_where_it_is(self):
        self.assertEqual(self.typed("x = [\n    |", "]"), "x = [\n    ]|")
        self.assertEqual(self.typed("x = |", "`"), "x = `|")  # 백틱은 파이썬의 쌍이 아님


class SetLangTest(EditorCase):
    lang = PYTHON

    def snapshot(self):
        return [guikit.painted(self.ed, line) for line in range(self.ed.blockCount())], self.states()

    def test_switching_language_and_back_restores_the_coloring_and_the_block_states(self):
        self.ed.setPlainText('def f():\n    """doc\n    line"""\n    return self.x  # note\n`a\nb`\n')
        before = self.snapshot()
        self.assertEqual(before[1], [0, 2, 0, 0, 0, 0, 0])  # 2 줄에서 연 삼중 따옴표가 3 줄로 이어짐
        self.assertEqual(before[0][3], [("return", "keyword"), ("self", "self"), ("# note", "comment")])
        self.ed.set_lang(JAVASCRIPT)
        self.assertIs(self.ed.lang, JAVASCRIPT)
        self.assertIs(self.ed.highlighter.lang, JAVASCRIPT)
        during = self.snapshot()
        self.assertNotEqual(during, before)
        self.assertEqual(during[1], [0, 0, 0, 0, 1, 0, 0])  # 백틱이 이어지고 삼중 따옴표는 이어지지 않음
        self.assertEqual(during[0][3], [("return", "keyword")])  # self 와 # 은 자바스크립트에서 뜻이 없음
        self.ed.set_lang(PYTHON)
        self.assertIs(self.ed.lang, PYTHON)
        self.assertEqual(self.snapshot(), before)

    def test_code_panel_passes_the_language_and_the_paste_option_through(self):
        default = widgets.CodePanel()
        self.assertEqual((default.editor.lang, default.editor.allow_paste), (PYTHON, False))
        panel = widgets.CodePanel(lang=JAVASCRIPT, paste=True)
        self.assertEqual((panel.editor.lang, panel.editor.allow_paste), (JAVASCRIPT, True))
        panel.set_code("const x = 1;")
        self.assertEqual(guikit.painted(panel.editor, 0), [("const", "keyword"), ("1", "number")])


class PasteTest(unittest.TestCase):
    def setUp(self):
        self.plain = CodeEditor()
        self.rich = CodeEditor(lang=JAVASCRIPT, paste=True)
        for ed in (self.plain, self.rich):
            ed.setFont(theme.code_font())
        self.data = QMimeData()
        self.data.setHtml("<p><b>let</b> x = 1;<br><i>let</i> y = 2;</p>")
        self.data.setText("let x = 1;\nlet y = 2;")

    def test_default_editor_still_refuses_every_paste(self):
        self.assertFalse(self.plain.canInsertFromMimeData(self.data))
        self.plain.insertFromMimeData(self.data)
        QGuiApplication.clipboard().setText("붙여넣을 글")
        self.plain.paste()
        QTest.keySequence(self.plain, QKeySequence(QKeySequence.StandardKey.Paste))
        self.assertEqual(self.plain.toPlainText(), "")

    def test_paste_editor_takes_the_text_only(self):
        self.assertTrue(self.rich.canInsertFromMimeData(self.data))
        self.rich.insertFromMimeData(self.data)
        self.assertEqual(self.rich.toPlainText(), "let x = 1;\nlet y = 2;")  # 서식은 빠지고 글자만 남음
        self.assertEqual(self.rich.textCursor().position(), len("let x = 1;\nlet y = 2;"))  # 커서는 붙여 넣은 글 뒤
        self.assertEqual(guikit.painted(self.rich, 0), [("let", "keyword"), ("1", "number")])  # 붙여 넣은 글도 칠해짐
        QGuiApplication.clipboard().setText("붙여넣을 글")
        self.rich.paste()
        self.assertEqual(self.rich.toPlainText(), "let x = 1;\nlet y = 2;붙여넣을 글")
        self.rich.selectAll()
        QTest.keySequence(self.rich, QKeySequence(QKeySequence.StandardKey.Paste))  # 단축키로도 들어가고 선택한 글을 바꿈
        self.assertEqual(self.rich.toPlainText(), "붙여넣을 글")
        empty = QMimeData()
        self.assertFalse(self.rich.canInsertFromMimeData(empty))  # 글자가 없는 것은 받지 않음
        self.rich.insertFromMimeData(empty)
        self.assertEqual(self.rich.toPlainText(), "붙여넣을 글")

    def test_windows_line_ends_become_plain_lines(self):
        data = QMimeData()
        data.setText("a\r\nb")
        self.rich.insertFromMimeData(data)
        self.assertEqual(self.rich.toPlainText(), "a\nb")
        self.assertEqual(self.rich.blockCount(), 2)


if __name__ == "__main__":
    unittest.main()
