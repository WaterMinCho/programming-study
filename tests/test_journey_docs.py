# -*- coding: utf-8 -*-
"""mdlite 의 이미지 줄(해설 그림)과 기존 블록 결과. PyQt6 없이 돎.

실행: python -m unittest tests.test_journey_docs
"""
import glob
import hashlib
import os
import sys
import unittest

os.environ.setdefault("STUDY_NODE_PROBE", "0")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import mdlite  # noqa: E402

# 블록 종류를 모두 담은 글. 아래 세 값은 이미지 줄을 더하기 전의 mdlite 로 한 번 계산해 박은 것임
PIECES = ["# 제목", "문단 첫 줄\n이어지는 줄 `x` **굵게**", "- 항목 하나\n- 항목 둘\n\n  ```python\n  x = 1\n  ```", "3. 셋째\n4. 넷째",
          "> 인용 `코드`", "| a | b |\n|---|---|\n| 1 | **굵게** |", "```js\nlet y = 2;\n```"]  # 맨 바깥 블록 하나씩
SAMPLE = "\n\n".join(PIECES) + "\n"
SAMPLE_BLOCKS = [
    {"t": "heading", "level": 1, "text": "제목"},
    {"t": "para", "text": "문단 첫 줄 이어지는 줄 `x` **굵게**"},
    {"t": "ul", "start": 1, "items": [[{"t": "para", "text": "항목 하나"}],
                                      [{"t": "para", "text": "항목 둘"}, {"t": "code", "lang": "python", "text": "x = 1"}]]},
    {"t": "ol", "start": 3, "items": [[{"t": "para", "text": "셋째"}], [{"t": "para", "text": "넷째"}]]},
    {"t": "quote", "blocks": [{"t": "para", "text": "인용 `코드`"}]},
    {"t": "table", "head": ["a", "b"], "rows": [["1", "**굵게**"]]},
    {"t": "code", "lang": "js", "text": "let y = 2;"},
]
SAMPLE_HTML_SHA = "55f76f56556a3270459cfe977f0e059dfd0f12116716026e78077588ee1a504b"
SAMPLE_EXPECTED = {
    "code_lines": ["x = 1", "let y = 2;"],
    "tables": [[["a", "b"], ["1", "굵게"]]],
    "ol_numbers": [3, 4],
    "inline_code": ["x", "코드"],
    "bold": ["굵게", "굵게"],
    "plain": ["제목", "문단 첫 줄 이어지는 줄 ", "x", " ", "굵게", "항목 하나", "항목 둘", "x = 1", "셋째", "넷째", "인용 ", "코드",
              "a", "b", "1", "굵게", "let y = 2;"],
}


def kinds(blocks):
    """블록 목록 안(목록 항목·인용 포함)의 모든 블록 종류."""
    found = []
    for block in blocks:
        found.append(block["t"])
        for item in block.get("items", []):
            found += kinds(item)
        found += kinds(block.get("blocks", []))
    return found


class ImageLineTest(unittest.TestCase):
    def test_whole_line_is_an_image_block(self):
        self.assertEqual(mdlite.parse("![그림 1-1a. 장부 줄이 품목 칸으로 모이는 모습](assets/1-1a.gif)"),
                         [{"t": "image", "alt": "그림 1-1a. 장부 줄이 품목 칸으로 모이는 모습", "src": "assets/1-1a.gif"}])
        self.assertEqual(mdlite.parse("![](assets/a.png)   "), [{"t": "image", "alt": "", "src": "assets/a.png"}])
        caption = "그림 3-Bc. 위치를 s + (K - cnt - 1) × D로 구하는 모습"  # 캡션 안의 괄호
        self.assertEqual(mdlite.parse("![%s](assets/3-bc.png)" % caption), [{"t": "image", "alt": caption, "src": "assets/3-bc.png"}])

    def test_image_sits_between_other_blocks(self):
        blocks = mdlite.parse("## 관찰\n문단\n\n![그림](assets/a.gif)\n## 풀이\n| a |\n|---|\n| 1 |\n![표 아래](assets/b.png)\n")
        self.assertEqual([b["t"] for b in blocks], ["heading", "para", "image", "heading", "table", "image"])
        self.assertEqual([b["src"] for b in blocks if b["t"] == "image"], ["assets/a.gif", "assets/b.png"])

    def test_image_text_inside_a_paragraph_list_or_quote_stays_text(self):
        self.assertEqual(mdlite.parse("글 앞 ![a](b.png) 글 뒤"), [{"t": "para", "text": "글 앞 ![a](b.png) 글 뒤"}])
        self.assertEqual(mdlite.parse("문단\n![a](b.png)"), [{"t": "para", "text": "문단 ![a](b.png)"}])
        self.assertEqual(mdlite.parse("- ![a](b.png)"), [{"t": "ul", "start": 1, "items": [[{"t": "para", "text": "![a](b.png)"}]]}])
        self.assertEqual(mdlite.parse("> ![a](b.png)"), [{"t": "quote", "blocks": [{"t": "para", "text": "![a](b.png)"}]}])
        self.assertEqual(mdlite.parse("![a](b c.png)"), [{"t": "para", "text": "![a](b c.png)"}])  # 경로에 빈칸이 있으면 그림이 아님
        self.assertNotIn("<img", mdlite.to_html("글 앞 ![a](b.png) 글 뒤\n\n- ![a](b.png)"))
        self.assertIn("![a](b.png)", mdlite.inline_plain("글 앞 ![a](b.png) 글 뒤"))

    def test_html_centers_the_picture_and_its_caption(self):
        self.assertEqual(mdlite.to_html("![캡션 <1> & 끝](assets/a.gif)"),
                         '<body><p align="center"><img src="assets/a.gif"></p>'
                         '<p class="muted" align="center">캡션 &lt;1&gt; &amp; 끝</p></body>')
        self.assertEqual(mdlite.blocks_html([{"t": "image", "alt": "", "src": 'a"b.png'}]),
                         '<body><p align="center"><img src="a&quot;b.png"></p><p class="muted" align="center"></p></body>')

    def test_expected_collects_image_sources_and_captions(self):
        exp = mdlite.expected("## 관찰\n\n![그림 1](assets/1-1a.gif)\n\n본문\n\n![](assets/1-1b.png)\n\n- ![목록](assets/x.png)\n")
        self.assertEqual(exp["images"], ["assets/1-1a.gif", "assets/1-1b.png"])
        self.assertIn("그림 1", exp["plain"])
        self.assertNotIn("", exp["plain"])
        self.assertEqual(mdlite.expected("본문")["images"], [])


class ExistingBlocksTest(unittest.TestCase):
    def test_sample_gives_the_same_blocks_html_and_expected_as_before(self):
        self.assertEqual(mdlite.parse(SAMPLE), SAMPLE_BLOCKS)
        self.assertEqual(hashlib.sha256(mdlite.to_html(SAMPLE).encode("utf-8")).hexdigest(), SAMPLE_HTML_SHA)
        exp = mdlite.expected(SAMPLE)
        self.assertEqual(exp.pop("images"), [])
        self.assertEqual(exp, SAMPLE_EXPECTED)

    def test_image_lines_only_add_blocks(self):
        """블록 사이에 이미지 줄을 끼워도 나머지 블록은 그대로임."""
        mixed = "\n".join(piece + "\n\n![그림 %d](assets/%d.png)\n" % (n, n) for n, piece in enumerate(PIECES))
        blocks = mdlite.parse(mixed)
        self.assertEqual([b for b in blocks if b["t"] != "image"], SAMPLE_BLOCKS)
        self.assertEqual([b["src"] for b in blocks if b["t"] == "image"], ["assets/%d.png" % n for n in range(len(PIECES))])

    def test_python_bank_has_no_image_blocks(self):
        files = glob.glob(os.path.join(ROOT, "problems", "**", "*.md"), recursive=True)
        self.assertTrue(files)
        for path in files:
            with open(path, encoding="utf-8") as handle:
                self.assertNotIn("image", kinds(mdlite.parse(handle.read())), path)


if __name__ == "__main__":
    unittest.main()
