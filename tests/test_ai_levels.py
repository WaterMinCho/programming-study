# -*- coding: utf-8 -*-
"""세 수준 블록(ai-levels) 읽기 테스트. 고정 은행 tests/ai_bank 의 l90 90a 2단계 끝 블록과 테스트 안에서 고친 JSON 으로
aiprep.bank 의 parse_page 꼴, 은행 오류, split_levels 조각 순서, level_parts 순서를 봄.

실행: python -m unittest tests.test_ai_levels
"""
import copy
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from aiprep import bank  # noqa: E402

FIXTURE = os.path.join(ROOT, "tests", "ai_bank")


def fixture_block():
    """고정 은행 l90 의 ai-levels 울타리 안 JSON(dict)."""
    with open(os.path.join(FIXTURE, "learn", "l90", "page.md"), encoding="utf-8") as handle:
        text = handle.read()
    body = text.split("```ai-levels\n", 1)[1].split("\n```", 1)[0]
    return json.loads(body)


class BankLevelsTest(unittest.TestCase):
    def setUp(self):
        self.data = fixture_block()

    def parse(self, data=None, folder="/bank/l90"):
        return bank._levels_block(json.dumps(self.data if data is None else data, ensure_ascii=False), folder)

    def broken(self, change):
        data = copy.deepcopy(self.data)
        change(data)
        found = self.parse(data)
        self.assertEqual(["error", "kind"], sorted(found), found)
        return found["error"]

    def test_parse_page_shape(self):
        note = bank.load_note({"id": "l90", "title": "90차시 시험 노트"}, FIXTURE)
        step = note["units"]["90a"]["steps"][1]
        block = step["blocks"][-1]
        self.assertEqual(("levels", "v1", "기울기"), (block["kind"], block["id"], block["concept"]))
        self.assertEqual([7, 15, 20], [level["level"] for level in block["levels"]])
        self.assertEqual(["v1"] * 3, [level["id"] for level in block["levels"]])  # 떠올리기처럼 block.get("id") 로 기록함
        keys = {"level", "id", "text", "q", "answer", "mode", "places", "unit", "why", "code", "mistake", "where", "figure"}
        for level in block["levels"]:
            self.assertEqual(keys, set(level))
            self.assertEqual("figure", level["figure"]["kind"])
            self.assertTrue(os.path.isfile(level["figure"]["path"]), level["figure"]["path"])
        seven, fifteen, twenty = block["levels"]
        self.assertEqual(("", "", ""), (seven["code"], seven["mistake"], seven["where"]))
        self.assertEqual(("", "", ""), (fifteen["code"], fifteen["mistake"], fifteen["where"]))
        self.assertEqual(5, len(twenty["code"].split("\n")))
        self.assertEqual((["3.6"], "number", None, ""), (seven["answer"], seven["mode"], seven["places"], seven["unit"]))

    def test_places_and_unit(self):
        data = copy.deepcopy(self.data)
        data["levels"][1].update(places=1, unit="개")
        fifteen = self.parse(data)["levels"][1]
        self.assertEqual((1, "개"), (fifteen["places"], fifteen["unit"]))  # 떠올리기처럼 채점에 넘김
        for bad in ("3", True, -1, 1.5):
            self.assertIn("places 는 0 이상의 정수", self.broken(lambda d: d["levels"][1].update(places=bad)))
        self.assertIn("unit 는 글", self.broken(lambda d: d["levels"][1].update(unit=3)))

    def test_figure_path_and_default_mode(self):
        data = copy.deepcopy(self.data)
        del data["levels"][1]["mode"]
        found = self.parse(data)
        self.assertEqual(os.path.join("/bank/l90", "assets", "90a-21.png"), found["levels"][0]["figure"]["path"])
        self.assertEqual("word", found["levels"][1]["mode"])
        del data["levels"][2]["figure"]
        self.assertIsNone(self.parse(data)["levels"][2]["figure"])  # 꼴로는 빠져도 됨(있어야 하는지는 verify_ai 가 봄)
        self.assertEqual("", bank._levels_block(json.dumps(self.data), None)["levels"][0]["figure"]["path"])

    def test_errors(self):
        self.assertIn("JSON 을 읽을 수 없습니다", bank._levels_block('{"id": "v1",', None)["error"])
        self.assertIn("JSON 객체", bank._levels_block("[]", None)["error"])
        self.assertIn("모르는 키", self.broken(lambda d: d.update(title="x")))
        self.assertIn("7·15·20 순서", self.broken(lambda d: d["levels"].reverse()))
        self.assertIn("7·15·20 순서", self.broken(lambda d: d["levels"].pop()))
        self.assertIn("7·15·20 순서", self.broken(lambda d: d["levels"][0].update(level=7.0)))
        self.assertIn("7살 수준에 쓸 수 없는 키가 있습니다: code", self.broken(lambda d: d["levels"][0].update(code="x = 1")))
        self.assertIn("15살 수준에 쓸 수 없는 키가 있습니다: where", self.broken(lambda d: d["levels"][1].update(where="1차시")))
        self.assertIn("쓸 수 없는 키가 있습니다: anwser", self.broken(lambda d: d["levels"][2].update(anwser=["6"])))
        self.assertIn("text 는 글", self.broken(lambda d: d["levels"][0].update(text=["글"])))
        self.assertIn("answer 는 비지 않은 글 목록", self.broken(lambda d: d["levels"][0].update(answer=[])))
        self.assertIn("answer 는 비지 않은 글 목록", self.broken(lambda d: d["levels"][0].update(answer=[3.6])))
        self.assertIn("figure 는", self.broken(lambda d: d["levels"][0]["figure"].pop("content")))
        self.assertIn("figure 는", self.broken(lambda d: d["levels"][0].update(figure="assets/90a-21.png")))
        self.assertIn("assets/ 아래 .png", self.broken(lambda d: d["levels"][0]["figure"].update(file="assets/90a-21.gif")))
        self.assertIn("assets/ 아래 .png", self.broken(lambda d: d["levels"][0]["figure"].update(file="../l01/assets/1b-41.png")))
        self.assertIn("``` 나 ~~~ 를 쓰지 않습니다", self.broken(lambda d: d["levels"][1].update(text="```python 은 쓰지 않습니다.")))
        self.assertIn("``` 나 ~~~ 를 쓰지 않습니다", self.broken(lambda d: d["levels"][2].update(text="글입니다.\n~~~\n코드로 보입니다.")))
        self.assertIn("15살 수준의 mode 를 모릅니다: nums", self.broken(lambda d: d["levels"][1].update(mode="nums")))

    def test_broken_block_is_one_error_block(self):
        page = "# 노트\n\n## 단원\n\n### 둘째\n\n글입니다.\n\n```ai-levels\n{\"id\": \"v1\", \"levels\": []}\n```\n"
        parsed = bank.parse_page(page, {"90a": "단원"})
        blocks = parsed["units"]["90a"]["steps"][0]["blocks"]
        self.assertEqual(["text", "levels"], [b["kind"] for b in blocks])
        self.assertEqual({"kind", "error"}, set(blocks[1]))

    def test_split_levels_order(self):
        block = json.dumps(self.data, ensure_ascii=False)
        page = "\n".join(["# 노트", "", "## 단원", "", "### 먼저 풀어 보기", "글", "", "### 2026 흐름", "흐름", "", "### 둘째",
                          "```python", "### 코드 안 줄", "```", "", "```ai-levels", block, "```", "뒤 글", "",
                          "## 그림 출처", "", "### 셋째", "```ai-levels", "{", "```"])
        parts = bank.split_levels(page, {"90a": "단원"})
        self.assertEqual(["main", "levels", "main", "levels"], [p[0] for p in parts])
        self.assertEqual([1, 16, 19, 24], [p[2] for p in parts])
        self.assertEqual(("90a", 2), (parts[1][1]["unit"], parts[1][1]["step"]))  # 2026 흐름과 코드 안 ### 는 세지 않음
        self.assertEqual("v1", parts[1][1]["id"])
        self.assertIn("### 코드 안 줄", parts[0][1])
        self.assertTrue(parts[2][1].startswith("뒤 글"))
        self.assertIsNone(parts[3][1]["unit"])  # sections 에 없는 ##
        self.assertIn("error", parts[3][1])
        self.assertNotIn("unit", bank.split_levels(page)[1][1])
        self.assertEqual("\n".join(p[1] if p[0] == "main" else "" for p in parts).count("ai-levels"), 0)

    def test_level_parts_order(self):
        twenty = self.parse()["levels"][2]
        names = [name for name, _ in bank.level_parts(twenty)]
        self.assertEqual(["text", "caption", "content", "code", "mistake", "where", "q", "why"], names)
        seven = dict(self.parse()["levels"][0], why="", figure=None)
        self.assertEqual(["text", "q"], [name for name, _ in bank.level_parts(seven)])


if __name__ == "__main__":
    unittest.main()
