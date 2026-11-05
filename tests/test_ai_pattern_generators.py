# -*- coding: utf-8 -*-
"""상황별 수치 문항의 공개 범위·풀이·시드 복원·출제 검사를 임시 은행에서 확인함."""
import json
import random
import unittest
from pathlib import Path
from types import SimpleNamespace

from aiprep import bank, gen, grade, service, skel
from tests.test_ai_service import PatternBase
from tests.test_ai_tools import NAMES, PatternCase, quiet
from tools import ai_mock_rules, ai_overlap, ai_seal, verify_ai


def add_generator(root):
    root = Path(root)
    folder = root / "items/pc"
    (folder / "gens.py").write_text('''from aiprep.gen import blank, gen

@gen("pc-g90", unit="18a", step="18a/1", facts=["F18-90"],
     tags=["묶음 수"], ref=["90차시 노트북 01 [2]"], basis="lecture-formula")
def batches(r):
    """남은 표본도 한 묶음에 담음."""
    n, size = r.int(20, 180), r.int(3, 12)
    return blank(stem=f"표본 {n}개를 한 묶음에 {size}개씩 담습니다. 마지막 남은 표본도 포함하면 전체 묶음 수는 ____ 입니다.",
                 blanks=[{"answer": [str((n+size-1)//size)], "mode": "number"}],
                 explain="남은 표본이 있으면 한 묶음을 더 만듭니다.", params={"n": n, "size": size})

@gen("pc-g91", unit="18b", step="18b/1", facts=["F18-90"],
     tags=["묶음 수"], ref=["90차시 노트북 01 [2]"], basis="lecture-formula")
def unpublished(r):
    raise ValueError("아직 공개하지 않은 단원임")
''', encoding="utf-8")
    (folder / "oracle.py").write_text('''def pc_g90(p):
    count, rest = divmod(p["n"], p["size"])
    return [str(count + bool(rest))]
''', encoding="utf-8")
    path = folder / "meta.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["units"]["18a"]["gen"] = ["pc-g90"]
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    path = folder / "work/facts.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["facts"].append({"id": "F18-90", "from": "수치 확인", "text": "나머지가 있으면 묶음을 하나 더 만듭니다.",
                          "verdict": "맞음", "where": ["90차시 노트북 01 [2]"], "checked": "2026-11-05"})
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    path = root / "learn/l18/page.md"
    text = path.read_text(encoding="utf-8").replace("<!-- facts: F18-01 F18-02 F18-03 -->",
                                                   "<!-- facts: F18-01 F18-02 F18-03 F18-90 -->", 1)
    path.write_text(text, encoding="utf-8")


def repeated_change():
    before = ["for p in model.parameters():", "    p.requires_grad = False",
              "for p in model.layer4.parameters():", "    p.requires_grad = False",
              "params = list(model.fc.parameters())", "keep()"]
    after = list(before)
    after[3] = "    p.requires_grad = True"
    after[4] = "params = list(model.layer4.parameters()) + list(model.fc.parameters())"
    skeleton = {"id": "S90", "variants": {"A": {"situation": "원래 코드입니다.", "lines": before},
                                            "B": {"situation": "바꾼 코드입니다.", "lines": after}}}
    card = {"id": "pc-x90", "kind": "skel", "part": "change", "pattern": "S90", "entry": {
        "id": "pc-x90", "from": "A", "to": "B", "stem": "고칠 줄을 모두 고르세요.",
        "back": "원래 판으로 돌릴 때 고칠 줄을 모두 고르세요."}}
    return card, skeleton


class PatternGeneratorServiceTest(PatternBase):
    def setUp(self):
        super().setUp()
        add_generator(self.root)

    def test_read_core_practice_and_wrong_note_keep_the_seed_and_place(self):
        sess = self.session()
        self.assertEqual({}, sess.errors)
        self.assertNotIn("pc-g91", sess.cards)
        self.assertNotIn("pc-g90", service.build_set(sess, sess._state(), "mixed", random.Random(1)))
        sess.mark_read("pc", "18a")
        first = sess.start_set("unit", lesson="pc", unit="18a", seed=1)
        self.assertNotIn("pc-g90", [e["card"] for e in first.queue])
        for cid in ("pc-k01", "pc-o01", "pc-p01"):
            self.answer(sess, cid)
            self.answer(sess, cid, day="10")
        self.at = "2026-11-12T20:00:00"
        practice = sess.start_set("unit", lesson="pc", unit="18a", seed=4)
        self.assertIn("pc-g90", [e["card"] for e in practice.queue])
        while practice.current()["card"] != "pc-g90":
            practice.answer(self.right(practice, practice.current()), 1, True)
            practice.next()
        view = practice.current()
        self.assertEqual(["학습 루프", "빈칸", "숫자 바뀜"], view["chips"])
        practice.answer(["-1"], 2, True)
        self.assertEqual(view["stem"], sess.wrong_item("pc-g90")["stem"])
        restored = self.session()
        self.assertEqual(view["stem"], restored.wrong_item("pc-g90")["stem"])
        target = restored.note_target("pc-g90")
        self.assertEqual(("pc", "18a/1"), (target["lesson"], target["step"]))
        self.assertEqual("상황별 코드", restored.wrong_notes()[0]["title"])
        self.assertEqual("i90", restored.card_info("pc-g90")["after"])


class PatternChangeRecordTest(PatternBase):
    def prepared_session(self):
        sess = self.session()
        card, skeleton = repeated_change()
        sess.skeletons["S90"] = skeleton
        sess.cards[card["id"]] = dict(sess.cards["pc-x01"], **card)
        return sess

    def test_legacy_record_keeps_the_old_option_numbers_and_bytes(self):
        sess = self.prepared_session()
        sess._append({"kind": "answer", "set": "legacy", "card": "pc-x90", "result": "stuck",
                      "seed": 2, "picked": [1], "again": 0})
        path = Path(sess.record.path)
        original = path.read_bytes()
        restored = self.prepared_session()
        detail = restored.wrong_item("pc-x90")
        self.assertEqual(["for p in model.parameters():", "for p in model.layer4.parameters():",
                          "p.requires_grad = False", "params = list(model.fc.parameters())", "keep()"], detail["options"])
        self.assertEqual(["for p in model.layer4.parameters():"], detail["mine"])
        self.assertNotIn("change_rev", restored.record.log[-1])
        self.assertEqual(original, path.read_bytes())

    def test_new_wrong_record_restores_its_display_and_selected_text(self):
        sess = self.prepared_session()
        practice = service.PracticeSet(sess, "new", "unit", ["pc-x90"], 1)
        practice.queue[0]["seed"] = 2
        current = practice.current()
        picked = current["options"][1]
        practice.answer([picked["no"]], 2, True)
        self.assertEqual(2, sess.record.log[-1]["change_rev"])
        restored = self.prepared_session().wrong_item("pc-x90")
        self.assertEqual([o["text"] for o in current["options"]], restored["options"])
        self.assertEqual([picked["text"]], restored["mine"])

    def test_seed_zero_wrong_note_restores_distinct_options_and_my_answer(self):
        sess = self.prepared_session()
        source = sess.cards["pc-x90"]
        sess.cards["pc-x04"] = dict(source, id="pc-x04", entry=dict(source["entry"], id="pc-x04"))
        practice = service.PracticeSet(sess, "seed-zero", "unit", ["pc-x04"], 1)
        practice.queue[0]["seed"] = 0
        current = practice.current()
        shown = practice._view(practice.queue[0])["item"]
        other = skel.view(sess.cards["pc-x04"], sess.skeletons["S90"], 1)
        self.assertNotEqual(shown["options"], other["options"])
        picked = current["options"][0]
        self.assertFalse(shown["options"][picked["no"]]["ok"])
        self.assertEqual("stuck", practice.answer([picked["no"]], 2, True)["result"])
        path = Path(sess.record.path)
        saved = path.read_bytes()
        restored = self.prepared_session()
        restored.cards["pc-x04"] = sess.cards["pc-x04"]
        detail = restored.wrong_item("pc-x04")
        self.assertEqual((0, 2), (restored.record.log[-1]["seed"], restored.record.log[-1]["change_rev"]))
        self.assertEqual(shown["stem"], detail["stem"])
        self.assertEqual([o["text"] for o in shown["options"]], detail["options"])
        self.assertEqual([picked["text"]], detail["mine"])
        self.assertEqual(saved, path.read_bytes())

    def test_only_missing_or_none_seed_falls_back_to_one(self):
        sess = self.prepared_session()
        for cid in ("pc-x90", "i90-g01", "i90-g02"):
            for row in ({}, {"seed": None}):
                with self.subTest(card=cid, row=row):
                    self.assertEqual(sess._static_view(sess.cards[cid], {"seed": 1}),
                                     sess._static_view(sess.cards[cid], row))

    def test_seed_zero_generator_blank_restores_problem_answer_and_my_input(self):
        sess = self.session()
        ps = service.PracticeSet(sess, "seed-zero", "unit", ["i90-g01"], 1)
        ps.queue[0]["seed"] = 0
        current = ps.current()
        item = ps._view(ps.queue[0])["item"]
        self.assertNotEqual(item["stem"], gen.run(sess.cards["i90-g01"]["gen"], 1)["stem"])
        self.assertEqual("stuck", ps.answer(["틀림"], 2, False)["result"])
        restored = self.session()
        detail = restored.wrong_item("i90-g01")
        self.assertEqual(0, restored.record.log[-1]["seed"])
        self.assertEqual(current["stem"], detail["stem"])
        self.assertEqual(["틀림"], detail["mine"])
        self.assertEqual([b["answer"][0] for b in item["blanks"]], restored.explain("i90-g01")["answer"])

    def test_seed_zero_generator_choice_restores_options_and_my_answer(self):
        sess = self.session()
        ps = service.PracticeSet(sess, "seed-zero", "unit", ["i90-g02"], 1)
        ps.queue[0]["seed"] = 0
        ps.current()
        item = ps._view(ps.queue[0])["item"]
        other = gen.run(sess.cards["i90-g02"]["gen"], 1)
        wrong = next(n for n, option in enumerate(item["options"]) if not option["ok"])
        self.assertNotEqual(item["stem"], other["stem"])
        self.assertNotEqual(item["options"][wrong]["text"], other["options"][wrong]["text"])
        self.assertEqual("stuck", ps.answer([wrong], 2, False)["result"])
        restored = self.session()
        detail = restored.wrong_item("i90-g02")
        self.assertEqual(0, restored.record.log[-1]["seed"])
        self.assertEqual(item["stem"], detail["stem"])
        self.assertEqual([o["text"] for o in item["options"]], detail["options"])
        self.assertEqual([item["options"][wrong]["text"]], detail["mine"])

    def test_answers_and_dont_know_keep_the_revision_and_direction(self):
        for back in (False, True):
            for action in ("answer", "dont_know"):
                with self.subTest(back=back, action=action):
                    sess = self.prepared_session()
                    practice = service.PracticeSet(sess, "direction", "unit", ["pc-x90"], 1)
                    practice.queue[0].update(seed=0, again=int(back))
                    shown = practice._view(practice.queue[0])["item"]
                    if action == "answer":
                        practice.answer(grade.right_options(shown), 2, True)
                    else:
                        practice.dont_know(2)
                    row = sess.record.log[-1]
                    self.assertEqual((2, 0, back), (row["change_rev"], row["seed"], bool(row.get("back"))))
                    self.assertEqual(shown, sess._static_view(sess.cards["pc-x90"], row))


class PatternGeneratorToolsTest(PatternCase):
    def setUp(self):
        super().setUp()
        add_generator(self.bank)

    def test_numeric_oracle_and_signature_cover_the_generator(self):
        code, output = self.verify("pc", "--sign", *NAMES)
        self.assertEqual(0, code, output)
        review = json.loads(Path(self.bank, "items/pc/work/review.json").read_text(encoding="utf-8"))
        self.assertTrue({"gens.py", "oracle.py"} <= set(review["files"]))
        self.write("items/pc/oracle.py", "def pc_g90(p):\n    return ['-1']\n")
        self.assertFailsPc("oracle")

    def test_public_samples_are_answer_free_and_grade_through_the_same_tool(self):
        output = str(Path(self.tmp, "public"))
        code, message = quiet(ai_seal.main, ["brief", "pc", "--out", output, "--bank", self.bank])
        self.assertEqual(0, code, message)
        sheet = Path(output, "sheet.md").read_text(encoding="utf-8")
        answers = json.loads(Path(output, "answers.json").read_text(encoding="utf-8"))
        self.assertIn("## 생성기 pc-g90", sheet)
        self.assertNotIn("pc-g91", sheet)
        self.assertNotIn("params", sheet)
        self.assertEqual({str(n): [""] for n in range(1, 11)}, answers["pc-g90"])
        spec = next(s for s in gen.load_module(str(Path(self.bank, "items/pc/gens.py"))) if s.id == "pc-g90")
        answers = {"pc-g90": {str(n): [gen.run(spec, n)["blanks"][0]["answer"][0]] for n in range(1, 11)}}
        path = Path(self.tmp, "answers.json")
        path.write_text(json.dumps(answers), encoding="utf-8")
        code, message = self.verify("pc", "--answers", str(path))
        self.assertEqual(0, code, message)
        self.assertIn("맞음 1 / 1", message)

    def test_overlap_uses_published_numeric_samples(self):
        rows = ai_overlap.targets(self.bank, ["pc"])
        names = [row[0] for row in rows]
        self.assertEqual(ai_overlap.GEN_SAMPLES, sum(name.startswith("pc pc-g90 시드") for name in names))
        self.assertFalse(any("pc-g91" in name for name in names))

    def test_mock_practice_collects_only_one_copy_of_published_samples(self):
        index = bank.read_index(self.bank)
        sources = verify_ai._MockSources(self.bank, index, 7, skel.load_patterns(self.bank))
        samples = sources.practice_stems()
        self.assertEqual(["pc-g90@%d" % seed for seed in range(7)],
                         [cid for cid, _ in samples if cid.startswith("pc-g")])
        spec = next(s for s in gen.load_module(str(Path(self.bank, "items/pc/gens.py"))) if s.id == "pc-g90")
        duplicate = {"id": "m1-01", "stem": gen.run(spec, 0)["stem"]}
        self.assertTrue(ai_mock_rules.practice_problems([duplicate], samples))
        self.assertIs(samples, sources.practice_stems())


class PatternOptionContextTest(unittest.TestCase):
    def test_repeated_assignment_keeps_its_loop_and_source_position(self):
        card, skeleton = repeated_change()
        saw_both = False
        for seed in range(40):
            view = skel.change_view(card, skeleton, seed)
            assignments = [o for o in view["options"] if "p.requires_grad = False" in o["text"]]
            saw_both |= len(assignments) == 2
            for option in assignments:
                self.assertIn("# 원본", option["text"])
                self.assertEqual("model.layer4.parameters()" in option["text"], option["ok"])
                self.assertIn("for p in ", option["text"])
            self.assertEqual(len(view["options"]), len({o["text"] for o in view["options"]}))
        self.assertTrue(saw_both)

    def test_change_validator_accepts_context_labels_and_identical_changed_lines(self):
        for identical in (False, True):
            with self.subTest(identical=identical):
                card, skeleton = repeated_change()
                if identical:
                    skeleton["variants"]["B"]["lines"][1] = "    p.requires_grad = True"
                    skeleton["variants"]["B"]["lines"][4] = skeleton["variants"]["A"]["lines"][4]
                failures = []
                checker = SimpleNamespace(fail=lambda *args: failures.append(args))
                verify_ai.check_skel_change(checker, "pc", skeleton, card["entry"], card, 300)
                self.assertEqual([], failures)

    def test_current_public_choice_grades_with_the_same_revision(self):
        card, skeleton = repeated_change()
        lesson = SimpleNamespace(group={}, cards=[card], skeletons={"S90": skeleton})
        for seed in ai_seal.SKEL_SEEDS:
            view = ai_seal.skel_choice(card, skeleton, seed)
            self.assertEqual(skel.view(card, skeleton, seed), view)
            self.assertEqual(2, view["skel"]["change_rev"])
            order = ai_seal.skel_option_order(card, len(view["options"]))
            answer = {"picked": [pos + 1 for pos, at in enumerate(order) if view["options"][at]["ok"]]}
            key = "pc-x90 시드 %d" % seed
            self.assertEqual((True, key), verify_ai.grade_skel_answer(key, answer, [lesson], {}))

    def test_pick_options_share_the_same_outer_indentation(self):
        skeleton = {"id": "S90", "variants": {"A": {"situation": "코드 한 줄을 고릅니다.", "lines": ["        out = model(x)"]}}}
        card = {"entry": {"variant": "A", "line": 0, "wrong": [
            {"text": "        out = other(x)"}, {"text": "    if ready:\n        out = other(x)"},
            {"text": "                out = empty()"}]}}
        options = skel.pick_view(card, skeleton)["options"]
        self.assertTrue(all(o["text"].splitlines()[0] == o["text"].splitlines()[0].lstrip() for o in options))
        self.assertEqual("if ready:\n    out = other(x)", options[2]["text"])
