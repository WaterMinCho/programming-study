# -*- coding: utf-8 -*-
"""상황별 코드 뼈대 테스트(aiprep/skel.py, grade.grade_skel, 설계 3.7). 고정 뼈대 tests/ai_bank_pc/patterns/S90.json 과 테스트 안에서
만든 작은 뼈대로 읽기, 카드 만들기, 점차 지우기, 뼈대 빈칸, 순서·줄·고칠 줄 고르기, 나란히 보기, 돌려 가며 빈칸을 봄.

실행: python -m unittest tests.test_ai_skel
"""
import copy
import difflib
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from aiprep import bank, grade, skel  # noqa: E402
from tests import aifix  # noqa: E402

GROUP = {"id": "pc", "page": "l18", "title": "상황별 코드", "units": {"18a": {"after": "i90", "name": "학습 루프"}}}
UNITS = {"18a": {"after": "i90", "name": "학습 루프", "title": "시험 뼈대 단원"}}


def fixture():
    return skel.load_patterns(aifix.PC_FILES)["S90"]


def make_cards(skeleton=None):
    skeleton = skeleton or fixture()
    return {c["id"]: c for c in skel.cards(GROUP, {"S90": skeleton}, UNITS)}


class LoadTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="ai_skel_")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def write(self, name, text):
        os.makedirs(os.path.join(self.tmp, "patterns"), exist_ok=True)
        with open(os.path.join(self.tmp, "patterns", name), "w", encoding="utf-8") as f:
            f.write(text)

    def test_reads_fixture_and_missing_folder(self):
        found = skel.load_patterns(aifix.PC_FILES)
        self.assertEqual(["S90"], list(found))
        self.assertEqual(["가", "나"], list(found["S90"]["variants"]))
        self.assertEqual({}, skel.load_patterns(self.tmp))

    def test_broken_file_and_wrong_id(self):
        self.write("S1.json", "{깨짐")
        with self.assertRaises(bank.AiBankError):
            skel.load_patterns(self.tmp)
        self.write("S1.json", json.dumps({"id": "S2", "variants": {"가": {"lines": ["a"]}}}))
        with self.assertRaises(bank.AiBankError) as caught:
            skel.load_patterns(self.tmp)
        self.assertIn("파일 이름", str(caught.exception))
        self.write("S1.json", json.dumps({"id": "S1", "variants": {"가": {"lines": "a"}}}))
        with self.assertRaises(bank.AiBankError):
            skel.load_patterns(self.tmp)

    def test_numeric_order_and_other_files(self):
        for sid in ("S10", "S2"):
            self.write("%s.json" % sid, json.dumps({"id": sid, "variants": {"가": {"lines": ["a"]}}}))
        self.write("notes.json", "{}")
        self.assertEqual(["S2", "S10"], list(skel.load_patterns(self.tmp)))


class CardsTest(unittest.TestCase):
    def test_fields_and_order(self):
        cards = skel.cards(GROUP, {"S90": fixture()}, UNITS)
        self.assertEqual(["pc-o01", "pc-p01", "pc-x01", "pc-k01", "pc-k02", "pc-k03", "pc-k04", "pc-k05", "pc-k06"], [c["id"] for c in cards])
        self.assertEqual(list(range(9)), [c["order"] for c in cards])
        by = {c["id"]: c for c in cards}
        k02 = by["pc-k02"]
        self.assertEqual(("skel", "slot", "pc", "18a", "18a/1", "S90", "가", "i90", "학습 루프"),
                         (k02["kind"], k02["part"], k02["lesson"], k02["unit"], k02["step"], k02["pattern"], k02["variant"],
                          k02["after"], k02["name"]))
        self.assertEqual("opt.____()", k02["head"])
        self.assertEqual("n += c.argmax(1).____()", by["pc-k06"]["head"])
        self.assertEqual("1번 축에서 고른 위치를 모두 더해 n 에 쌓는 줄로 옳은 것을 고르세요.", by["pc-p01"]["head"])
        self.assertEqual(skel.ORDER_HEAD, by["pc-o01"]["head"])
        self.assertEqual("나", by["pc-x01"]["variant"])
        self.assertEqual({"나", "가"}, set(by["pc-x01"]["situations"]))
        self.assertEqual((["학습 루프"], 3), (k02["tags"], k02["prio"]))
        self.assertEqual(("pc-count", "pc-k02"), (by["pc-k05"]["family"], k02["family"]))
        self.assertEqual((True, False, False), (by["pc-k01"]["core"], k02["core"], k02["deep"]))
        self.assertEqual(["X18-01"], by["pc-x01"]["errata"])

    def test_ref_and_level_are_not_inherited(self):
        skeleton = fixture()
        for key in ("ref", "level"):
            skeleton["slots"][0].pop(key)
        skeleton["slots"][0]["tags"] = ["모드"]
        card = make_cards(skeleton)["pc-k01"]
        self.assertEqual(([], 2, ["모드"]), (card["ref"], card["level"], card["tags"]))

    def test_unpublished_unit_has_no_cards(self):
        self.assertEqual([], skel.cards(GROUP, {"S90": fixture()}, {"18b": UNITS["18a"]}))

    def test_card_texts(self):
        cards = make_cards()
        texts = {where: (text, md) for where, text, md in skel.card_texts(cards["pc-p01"])}
        self.assertEqual(("묶음마다 파라미터를 한 번 바꾸며 학습합니다.", True), texts["pc-p01:가 코드 예제 상황"])
        self.assertTrue(texts["pc-p01:stem"][1])
        self.assertEqual(("n += c.argmax(0).sum()", False), texts["pc-p01:보기1"])
        self.assertIn("pc-p01:보기3 why", texts)
        self.assertEqual(("축을 0번으로 씀", False), texts["pc-p01:보기1 aim"])
        self.assertIn("pc-p01:explain", texts)
        texts = {where for where, _, _ in skel.card_texts(cards["pc-k02"])}
        self.assertEqual({"pc-k02:가 코드 예제 상황", "pc-k02:explain", "pc-k02:hint"}, texts)
        texts = {where for where, _, _ in skel.card_texts(cards["pc-x01"])}
        self.assertIn("pc-x01:나 코드 예제 상황", texts)
        self.assertIn("pc-x01:가 코드 예제 상황", texts)


class FadeTest(unittest.TestCase):
    def test_table(self):
        self.assertEqual(0, skel.fade([1] * 9 + [0]))
        self.assertEqual(1, skel.fade([1]))
        self.assertEqual(2, skel.fade([3] * 9 + [2]))
        self.assertEqual(3, skel.fade([3]))
        self.assertEqual(1, skel.fade([None, 2]))
        self.assertEqual(0, skel.fade([]))

    def test_main_box_counts(self):
        cards, skeleton = make_cards(), fixture()
        view = skel.slot_view(cards["pc-k02"], skeleton, {"pc-k02": 4, "pc-k03": None})
        self.assertEqual((2, ["pc-k03"]), (view["skel"]["fade"], view["skel"]["masked"]))


class SlotViewTest(unittest.TestCase):
    def setUp(self):
        self.cards, self.skeleton = make_cards(), fixture()

    def view(self, cid, boxes, **kw):
        return skel.slot_view(self.cards[cid], self.skeleton, boxes, **kw)

    def test_main_only_at_zero(self):
        view = self.view("pc-k02", {"pc-k02": None, "pc-k01": None, "pc-k03": None})
        self.assertEqual(1, len(view["blanks"]))
        self.assertEqual({"answer": ["zero_grad"], "mode": "code", "hint": "메서드 이름", "slot": "pc-k02", "main": True},
                         view["blanks"][0])
        self.assertIn("    opt.____()", view["stem"])
        self.assertTrue(view["stem"].startswith("묶음마다 파라미터를 한 번 바꾸며 학습합니다.\n\n빈칸에 들어갈 코드를 쓰세요.\n\n```python\n"))
        self.assertEqual({"part": "slot", "fade": 0, "masked": [], "whole": False}, view["skel"])
        self.assertEqual(skel.view(self.cards["pc-k02"], self.skeleton, 7)["stem"], view["stem"])

    def test_masked_order_and_position(self):
        boxes = {"pc-k02": 2, "pc-k01": 2, "pc-k03": 1, "pc-k05": 3}
        view = self.view("pc-k02", boxes)
        self.assertEqual(2, view["skel"]["fade"])
        self.assertEqual(["pc-k03", "pc-k01"], view["skel"]["masked"])  # 상자 1 이 먼저, 그다음 상자 2
        self.assertEqual(["pc-k01", "pc-k02", "pc-k03"], [b["slot"] for b in view["blanks"]])  # 코드 위치 순
        self.assertEqual([False, True, False], [b["main"] for b in view["blanks"]])
        self.assertNotIn("pc-k04", [b["slot"] for b in view["blanks"]])  # boxes 에 없는 자리는 가리지 않음
        self.assertEqual(4, view["stem"].count("____") + 1)

    def test_distance_breaks_ties(self):
        view = self.view("pc-k04", {"pc-k04": 2, "pc-k01": 2, "pc-k03": 2})
        self.assertEqual(["pc-k03", "pc-k01"], view["skel"]["masked"])

    def test_again_rotates_and_record_rebuilds(self):
        boxes = {"pc-k02": 2, "pc-k01": 2, "pc-k03": 1, "pc-k05": 3}
        first = self.view("pc-k02", boxes)
        second = self.view("pc-k02", boxes, again=1)
        self.assertEqual(["pc-k05", "pc-k03"], second["skel"]["masked"])
        self.assertNotEqual(first["skel"]["masked"], second["skel"]["masked"])
        again = self.view("pc-k02", {}, masked=second["skel"]["masked"] + ["pc-k99", "pc-k02"], whole=False)
        self.assertEqual(second["stem"], again["stem"])
        self.assertEqual(second["blanks"], again["blanks"])
        record = {"seed": 3, "fade": 2, "masked": second["skel"]["masked"], "whole": False}
        redrawn = skel.view(self.cards["pc-k02"], self.skeleton, 1, record=record)
        self.assertEqual((second["stem"], 2), (redrawn["stem"], redrawn["skel"]["fade"]))

    def test_whole_line(self):
        view = self.view("pc-k02", {"pc-k02": 4, "pc-k01": 4, "pc-k03": 3, "pc-k04": 4, "pc-k05": 3})
        self.assertEqual((3, True), (view["skel"]["fade"], view["skel"]["whole"]))
        self.assertIn("\n    ____\n", view["stem"])
        main = next(b for b in view["blanks"] if b["main"])
        self.assertEqual((["opt.zero_grad()", "opt.zero_grad(set_to_none=True)"], skel.LINE_HINT), (main["answer"], main["hint"]))
        view = self.view("pc-k03", {"pc-k03": 4, "pc-k01": 4, "pc-k02": 3})
        self.assertEqual((3, False), (view["skel"]["fade"], view["skel"]["whole"]))  # line_answer 가 없으면 토큰 빈칸

    def test_whole_line_drops_other_slots_on_that_line(self):
        skeleton = fixture()
        skeleton["slots"][4]["line_answer"] = ["n += c.argmax(1).sum()"]
        cards = make_cards(skeleton)
        view = skel.slot_view(cards["pc-k05"], skeleton, {"pc-k05": 4, "pc-k06": 3, "pc-k04": 3})
        self.assertTrue(view["skel"]["whole"])
        self.assertEqual(["pc-k04"], view["skel"]["masked"])
        self.assertIn("    ____", view["stem"])
        self.assertEqual(["pc-k04", "pc-k05"], [b["slot"] for b in view["blanks"]])

    def test_two_slots_on_one_line(self):
        view = self.view("pc-k05", {"pc-k05": 1, "pc-k06": 1})
        self.assertIn("n += c.____(1).____()", view["stem"])
        self.assertEqual(["pc-k05", "pc-k06"], [b["slot"] for b in view["blanks"]])
        graded = grade.grade_skel(view, ["argmax(1)", "sum"])
        self.assertEqual(("pass", {}), (graded["result"], graded["also"]))


class GradeSkelTest(unittest.TestCase):
    def setUp(self):
        self.view = skel.slot_view(make_cards()["pc-k02"], fixture(), {"pc-k02": 2, "pc-k01": 2, "pc-k03": 1, "pc-k05": 3})

    def test_main_right_other_wrong(self):
        graded = grade.grade_skel(self.view, ["eval", "zero_grad", "backward"])
        self.assertEqual({"result": "pass", "per_blank": [False, True, True], "also": {"pc-k01": "stuck"}}, graded)

    def test_main_wrong_and_empty(self):
        graded = grade.grade_skel(self.view, ["train", "step", "backward"])
        self.assertEqual(("stuck", {}), (graded["result"], graded["also"]))
        graded = grade.grade_skel(self.view, ["train", ""])
        self.assertEqual(("stuck", [True, False, False], {"pc-k03": "stuck"}), (graded["result"], graded["per_blank"], graded["also"]))

    def test_context_forms(self):
        view = skel.slot_view(make_cards()["pc-k02"], fixture(), {})
        for value in ("zero_grad", "zero_grad()", "opt.zero_grad()", ".zero_grad"):
            self.assertEqual("pass", grade.grade_skel(view, [value])["result"], value)
        self.assertEqual("stuck", grade.grade_skel(view, ["zerograd"])["result"])


class OrderTest(unittest.TestCase):
    def setUp(self):
        self.card, self.skeleton = make_cards()["pc-o01"], fixture()
        entry = self.card["entry"]
        lines = self.skeleton["variants"]["가"]["lines"]
        self.text = {tuple(p): "\n".join(skel.dedent([lines[entry["lines"][k]] for k in p])) for p in skel.order_wrongs(entry["valid"])}
        self.valid = {"\n".join(skel.dedent([lines[entry["lines"][k]] for k in p])) for p in entry["valid"]}

    def test_three_hundred_seeds(self):
        for seed in range(1, 301):
            view = skel.order_view(self.card, self.skeleton, seed)
            texts = [o["text"] for o in view["options"]]
            right = [o["text"] for o in view["options"] if o["ok"]]
            self.assertEqual(4, len(set(texts)), seed)
            self.assertEqual(1, len(right), seed)
            self.assertIn(right[0], self.valid)
            for option in view["options"]:
                if not option["ok"]:
                    self.assertNotIn(option["text"], self.valid)
                    self.assertIn(option["text"], self.text.values())
        self.assertEqual(skel.order_view(self.card, self.skeleton, 9), skel.order_view(self.card, self.skeleton, 9))

    def test_pinned_seed(self):
        view = skel.order_view(self.card, self.skeleton, 1)
        self.assertEqual(("choice", "right", False, True, 2, False, {"part": "order", "seed": 1}),
                         (view["kind"], view["pick"], view["multi"], view["code_options"], view["grid"], view["keep_order"], view["skel"]))
        self.assertEqual(["c = net(a)\nopt.step()\ne = crit(c, b)\ne.backward()\nopt.zero_grad()",
                          "opt.zero_grad()\nc = net(a)\ne = crit(c, b)\ne.backward()\nopt.step()",
                          "c = net(a)\nopt.zero_grad()\ne.backward()\nopt.step()\ne = crit(c, b)",
                          "e.backward()\nc = net(a)\nopt.zero_grad()\ne = crit(c, b)\nopt.step()"], [o["text"] for o in view["options"]])
        self.assertTrue(view["stem"].endswith(skel.ORDER_STEM))

    def test_wrongs_are_one_move_from_valid(self):
        wrongs = skel.order_wrongs([[0, 1, 2]])
        self.assertEqual([(0, 2, 1), (1, 0, 2), (1, 2, 0), (2, 0, 1)], wrongs)


class PickChangeTest(unittest.TestCase):
    def setUp(self):
        self.cards, self.skeleton = make_cards(), fixture()

    def test_pick(self):
        view = skel.pick_view(self.cards["pc-p01"], self.skeleton)
        self.assertEqual(4, len(view["options"]))
        self.assertEqual({"text": "n += c.argmax(1).sum()", "ok": True, "why": ""}, view["options"][0])
        self.assertEqual("축을 0번으로 씀", view["options"][1]["aim"])
        self.assertEqual((1, False, {"part": "pick"}), (view["grid"], view["keep_order"], view["skel"]))
        self.assertIn("**옳은**", view["stem"])

    def test_change_three_hundred_seeds(self):
        card = self.cards["pc-x01"]
        left, right = self.skeleton["variants"]["나"]["lines"], self.skeleton["variants"]["가"]["lines"]
        differ = set()
        for op, i1, i2, _, _ in difflib.SequenceMatcher(None, left, right, autojunk=False).get_opcodes():
            if op != "equal":
                differ |= {left[i].strip() for i in range(i1, i2)}
        order = [line.strip() for line in left]
        for seed in range(1, 301):
            view = skel.change_view(card, self.skeleton, seed)
            texts = [o["text"] for o in view["options"]]
            oks = [o["text"] for o in view["options"] if o["ok"]]
            self.assertTrue(4 <= len(texts) <= 5, seed)
            self.assertTrue(2 <= len(oks) <= 3, seed)
            self.assertEqual(set(oks), {t for t in texts if t in differ})
            self.assertEqual(sorted(texts, key=order.index), texts)
            self.assertEqual(len(set(texts)), len(texts))
        self.assertEqual((True, True, True, {"part": "change", "seed": 4, "back": False, "change_rev": 2}),
                         (view["multi"], view["keep_order"], view["code_options"], skel.change_view(card, self.skeleton, 4)["skel"]))

    def test_change_back(self):
        card = self.cards["pc-x01"]
        again = skel.view(card, self.skeleton, 5, again=1)
        self.assertFalse(again["skel"]["back"])  # back 지문이 없으면 다시 낼 때도 같은 방향
        skeleton = fixture()
        skeleton["changes"][0]["back"] = "학습 판(가)을 평가 판(나)으로 바꿀 때 고칠 줄을 **모두** 고르세요."
        card = make_cards(skeleton)["pc-x01"]
        again = skel.view(card, skeleton, 5, again=1)
        self.assertTrue(again["skel"]["back"])
        self.assertIn("net.train()", [o["text"] for o in again["options"] if o["ok"]])
        self.assertIn("학습 판(가)을", again["stem"])
        self.assertTrue(again["stem"].startswith("묶음마다"))
        self.assertFalse(skel.view(card, skeleton, 5)["skel"]["back"])
        self.assertTrue(skel.view(card, skeleton, 1, record={"seed": 5, "back": True})["skel"]["back"])


class DiffTest(unittest.TestCase):
    def test_fixture_pair(self):
        made = skel.diff(fixture(), "가", "나")
        self.assertEqual((2, 6, 8), (made["different"], made["same"], len(made["rows"])))
        self.assertEqual({"left": "net.train()", "right": "net.eval()", "same": False}, made["rows"][0])
        self.assertEqual({"left": "for a, b in data:", "right": "for a, b in data:", "same": True}, made["rows"][1])
        self.assertEqual(("S90", "가", "나"), (made["skel"], made["left"], made["right"]))
        with self.assertRaises(bank.AiBankError):
            skel.diff(fixture(), "가", "다")

    def test_split_zip_delete_insert(self):
        skeleton = {"id": "S99", "variants": {
            "A": {"lines": ["same()", "loss_sum += loss.item()", "xyz = 1", "extra_a = 1", "keep()", "end()"]},
            "B": {"lines": ["same()", "loss_sum += loss.item() * n", "completely_other(42)", "keep()", "end()"]}}}
        self.assertLess(difflib.SequenceMatcher(None, "xyz = 1", "completely_other(42)").ratio(), skel.SIMILAR)
        made = skel.diff(skeleton, "A", "B")
        self.assertEqual([("same()", "same()", True),
                          ("loss_sum += loss.item()", "loss_sum += loss.item() * n", False),  # 짝으로 남음
                          ("xyz = 1", None, False), (None, "completely_other(42)", False),  # 비슷하지 않아 풀림
                          ("extra_a = 1", None, False),  # zip 에서 남은 줄
                          ("keep()", "keep()", True), ("end()", "end()", True)],
                         [(r["left"], r["right"], r["same"]) for r in made["rows"]])
        self.assertEqual((4, 3), (made["different"], made["same"]))
        only = {"id": "S98", "variants": {"A": {"lines": ["a()", "b()", "c()"]}, "B": {"lines": ["a()", "c()", "d()"]}}}
        self.assertEqual([("a()", "a()", True), ("b()", None, False), ("c()", "c()", True), (None, "d()", False)],
                         [(r["left"], r["right"], r["same"]) for r in skel.diff(only, "A", "B")["rows"]])


class RotateTest(unittest.TestCase):
    def test_block(self):
        made = skel.rotate_block(fixture(), "가")
        self.assertEqual("\n".join(fixture()["variants"]["가"]["lines"]), made["code"])
        self.assertEqual(["pc-k01", "pc-k02", "pc-k03", "pc-k04", "pc-k05", "pc-k06"], [s["id"] for s in made["slots"]])
        for slot in made["slots"]:
            self.assertEqual(1, slot["code"].count("____"))
            self.assertEqual(made["code"], slot["code"].replace("____", slot["token"]))
        self.assertEqual({"id": "pc-k05", "line": 7, "token": "argmax", "hint": "메서드 이름", "mode": "code"},
                         {k: v for k, v in made["slots"][4].items() if k != "code"})
        part = skel.rotate_block(fixture(), "가", ["pc-k06", "pc-k01", "pc-k06"])
        self.assertEqual(["pc-k01", "pc-k06"], [s["id"] for s in part["slots"]])
        with self.assertRaises(bank.AiBankError):
            skel.rotate_block(fixture(), "가", ["pc-k77"])
        with self.assertRaises(bank.AiBankError):
            skel.rotate_block(fixture(), "다")
        self.assertEqual([], skel.rotate_block(fixture(), "나")["slots"])

    def test_next(self):
        queue = ["a", "b", "c", "d", "e", "f"]
        self.assertEqual((queue, 1), skel.rotate_next(queue, 0, True))
        self.assertEqual((["a", "b", "c", "d", "a", "e", "f"], 1), skel.rotate_next(queue, 0, False))
        self.assertEqual((["a", "b", "c", "d", "e", "f", "e"], 5), skel.rotate_next(queue, 4, False))  # 남은 게 적으면 맨 끝
        queue, pos = ["a"], 0
        queue, pos = skel.rotate_next(queue, pos, False)
        self.assertEqual((["a", "a"], 1), (queue, pos))
        queue, pos = skel.rotate_next(queue, pos, True)
        self.assertGreaterEqual(pos, len(queue))  # 끝

    def test_view_part_errors(self):
        card = dict(make_cards()["pc-k01"], part="other")
        with self.assertRaises(bank.AiBankError):
            skel.view(card, fixture(), 1)
        broken = copy.deepcopy(fixture())
        broken["slots"][0]["token"] = "nothere"
        with self.assertRaises(bank.AiBankError):
            skel.slot_spots(broken, "가")


class FencesTest(unittest.TestCase):
    def test_marks(self):
        text = "글\n<!-- skel: S90 가 -->\n\n```python\nnet.train()  # 모드\n```\n\n<!-- skel: S1 표준형 -->\n글만 있음\n"
        found = bank.skel_fences(text)
        self.assertEqual([{"skel": "S90", "variant": "가", "line": 2, "code": ["net.train()  # 모드"]},
                          {"skel": "S1", "variant": "표준형", "line": 8, "code": None}], found)
        self.assertEqual("글\n\n```python\nnet.train()  # 모드\n```\n\n글만 있음\n", bank.strip_marks(text))

    def test_number_blanks_in_code(self):
        stem = "글\n\n```python\na.____()\nb.____()\n```"
        self.assertEqual(stem, bank.number_blanks(stem))
        self.assertEqual("글\n\n```python\na.①____()\nb.②____()\n```", bank.number_blanks(stem, code=True))


if __name__ == "__main__":
    unittest.main()
