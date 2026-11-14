# -*- coding: utf-8 -*-
"""응용 생성기의 표시 조건·계산·단원 출제·기록 복원을 확인함."""
import ast
import copy
import json
import os
import random

from aiprep import bank, gen, service
from learning_data import generation
from learning_server import dataset, input_example
from tests.test_ai_service import Base


class ApplicationVariationTest(Base):
    def session(self):
        return service.AiSession("alice", home=os.path.join(self.tmp, "home"), root=bank.AI_DIR, course="app")

    def test_displayed_arrays_and_conditions_match_oracles_for_300_seeds(self):
        for lid in ("a01", "a03"):
            data = bank.load_items({"id": lid})
            spec, = data["gens"]
            oracle = gen.load_oracle(os.path.join(data["dir"], "oracle.py"))[gen.oracle_name(spec.id)]
            stems, conditions = set(), set()
            for seed in range(1, 301):
                item = gen.run(spec, seed)
                with self.subTest(generator=spec.id, seed=seed):
                    self.assertEqual(oracle(item["params"]), [b["answer"][0] for b in item["blanks"]])
                    code = item["stem"].split("```python\n")[1].split("```")[0]
                    nodes = ast.parse(code).body
                    arrays = {node.targets[0].id: ast.literal_eval(node.value.args[0])
                              for node in nodes if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call)
                              and isinstance(node.value.func, ast.Attribute) and node.value.func.attr == "array"}
                    params = item["params"]
                    if lid == "a01":
                        self.assertEqual({"a": [params["a"]], "b": [params["b"]]}, arrays)
                        totals = [a + b for a, b in zip(params["a"], params["b"])]
                        self.assertTrue(any(n < 255 for n in totals))
                        self.assertIn(255, totals)
                        self.assertTrue(any(n > 255 for n in totals))
                        conditions.add(len(totals))
                    else:
                        self.assertEqual(params["patch"], arrays["patch"])
                        self.assertIn("CV_64F, %s, ksize=3" % ("1, 0" if params["axis"] == "x" else "0, 1"), code)
                        self.assertEqual(params["absolute"], "abs(response[1, 1])" in code)
                        conditions.add((params["axis"], params["absolute"]))
                    source = bank.generation_source(spec)
                    captured = generation.capture(source, item, {})
                    self.assertEqual(params, captured["params"])
                    self.assertEqual(seed, captured["seed"])
                    self.assertEqual(spec.meta["template_revision"], captured["template_revision"])
                    stems.add(item["stem"])
            self.assertGreaterEqual(len(stems), 20)
            self.assertEqual({3, 4} if lid == "a01" else {("x", False), ("x", True), ("y", False), ("y", True)}, conditions)

    def test_uint8_oracle_covers_zero_exact_limit_and_overflow(self):
        oracle = gen.load_oracle(os.path.join(bank.items_dir("a01"), "oracle.py"))["a01_g01"]
        self.assertEqual(["[0, 255, 255, 255]", "[0, 255, 254, 44]"],
                         oracle({"a": [0, 128, 255, 200], "b": [0, 127, 255, 100]}))

    def test_sobel_oracle_preserves_sign_and_handles_transpose_and_flat_patch(self):
        oracle = gen.load_oracle(os.path.join(bank.items_dir("a03"), "oracle.py"))["a03_g01"]
        patch = [[10, 10, 40]] * 3
        for axis, values in (("x", patch), ("y", list(map(list, zip(*patch))))):
            self.assertEqual(["120"], oracle({"patch": values, "axis": axis, "absolute": False}))
            reverse = [row[::-1] for row in values] if axis == "x" else values[::-1]
            self.assertEqual(["-120"], oracle({"patch": reverse, "axis": axis, "absolute": False}))
            self.assertEqual(["120"], oracle({"patch": reverse, "axis": axis, "absolute": True}))
            self.assertEqual(["0"], oracle({"patch": [[25] * 3] * 3, "axis": axis, "absolute": False}))

    def test_new_cards_open_after_core_and_survive_short_unit_practice(self):
        sess = self.session()
        self.assertEqual({}, sess.errors)
        for lid, unit, cid in (("a01", "a1c", "a01-g01"), ("a03", "a3b", "a03-g01")):
            sess.mark_read(lid, unit)
            self.assertFalse(sess._state().eligible_new(sess.cards[cid]))
            cores = [c["id"] for c in sess.cards.values() if c["lesson"] == lid and c["unit"] == unit and c["core"]]
            for day in ("08", "09"):
                self.at = "2026-11-%sT20:00:00" % day
                for core in cores:
                    sess._append({"kind": "answer", "set": day, "card": core, "result": "pass", "again": 0})
            self.assertTrue(sess._state().eligible_new(sess.cards[cid]))
            chosen = service.build_set(sess, sess._state(), "unit", random.Random(7), lesson=lid, unit=unit)
            self.assertIn(cid, chosen)
            self.assertLessEqual(sum(sess.cards[c]["kind"] == "gen" for c in chosen), max(1, int(len(chosen) * service.GEN_SHARE)))
            self.assertEqual(len(chosen), len({sess.cards[c]["family"] for c in chosen}))

    def test_full_round_cap_and_protected_review_cards_still_apply(self):
        sess = self.session()
        generated = [c for c in sess.cards if sess.cards[c]["kind"] == "gen"]
        static = [c for c in sess.cards if sess.cards[c]["kind"] != "gen"]
        chosen = [(c, "new") for c in generated + static[:17]]
        self.assertEqual(20, len(service._gen_trim(sess, copy.deepcopy(chosen), minimum=1)))
        short = [(c, "new") for c in generated + static[:2]]
        trimmed = service._gen_trim(sess, copy.deepcopy(short), minimum=1)
        self.assertEqual(1, sum(sess.cards[c]["kind"] == "gen" for c, _ in trimmed))
        self.assertFalse(any(sess.cards[c]["kind"] == "gen" for c, _ in service._gen_trim(sess, copy.deepcopy(short))))
        protected = service._gen_trim(sess, copy.deepcopy(short), keep=generated)
        self.assertEqual(set(generated), {c for c, _ in protected if sess.cards[c]["kind"] == "gen"})

    def test_generation_reaches_model_input_and_saved_practice_restores_display(self):
        sess = self.session()
        sess.collection.set_enabled(True)
        provenance = []
        for cid in ("a01-g01", "a02-g01", "a03-g01"):
            practice = service.PracticeSet(sess, cid, "unit", [cid], 1)
            current = practice.current()
            content = practice._collection_item(practice.queue[0])["content"]
            value = content["generation"]
            self.assertEqual("declared", value["params_status"])
            self.assertEqual(cid, value["generator_id"])
            self.assertEqual(set(sess.cards[cid]["gen"].meta["display_params"]), set(value["params"]))
            self.assertFalse(set(value["params"]) & generation.RESERVED_PARAMS)
            self.assertNotIn("explain", content)
            snapshot = json.loads(json.dumps(practice.snapshot()))
            restored = service.PracticeSet.restore(sess, snapshot)
            self.assertEqual(current["stem"], restored.current()["stem"])
            self.assertEqual(value, restored._collection_item(restored.queue[0])["content"]["generation"])
            practice.answer(self.wrong(current), 1, False)
            self.assertEqual(current["stem"], sess.wrong_item(cid)["stem"])
            provenance.append(value)
        rows = dataset.prepare(sess.collection.snapshot())
        vocabulary = {"questions": ["<PAD>", "<UNK>"], "concepts": ["<PAD>", "<UNK>"]}
        batch = input_example.batch(rows, vocabulary)
        self.assertEqual(provenance, batch["question_provenance"]["query"])
        self.assertTrue(all(value["template_revision"] for value in provenance))
