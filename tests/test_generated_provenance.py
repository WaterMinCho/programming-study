# -*- coding: utf-8 -*-
"""임시 생성 문항의 수집·전송·입력 보존과 정답 누출·소급·줄바꿈 차이를 확인함."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import sys
from unittest import mock
import uuid

from aiprep import bank, gen, service
from learning_data import collection, generation, privacy
from learning_server import app, dataset, input_example, sample, starter
from tests.test_ai_service import Base, FIXTURE
from tests import test_learning_privacy, test_learning_server


class GeneratedProvenanceTest(Base):
    def setUp(self):
        super().setUp()
        self.root = str(Path(self.tmp) / "bank")
        shutil.copytree(FIXTURE, self.root)
        patcher = mock.patch("urllib.request.OpenerDirector.open", side_effect=AssertionError("외부 통신 금지"))
        patcher.start()
        self.addCleanup(patcher.stop)

    def declare_params(self, names):
        path = Path(self.root) / "items/i90/gens.py"
        text = path.read_text(encoding="utf-8")
        text += "\none_step.gen_spec.meta.update(template_revision='one-step-1', display_params=%r)\n" % (names,)
        path.write_text(text, encoding="utf-8")

    def practice(self, sess, name="generated", seed=3, card="i90-g01"):
        return service.PracticeSet(sess, name, "unit", [card], seed)

    def test_runtime_hash_is_frozen_at_gen_import_before_bank_loads_items(self):
        path = Path(self.tmp) / "runtime.py"
        source = Path(gen.__file__).read_text(encoding="utf-8")
        path.write_text(source, encoding="utf-8")
        runtime = gen._exec(str(path), "provenance_runtime")
        loaded_hash = runtime.RUNTIME_SOURCE_HASH
        self.assertEqual(bank._source_hash(path), loaded_hash)
        path.write_text(source + "\n# 다음 import에 적용할 버전임\n", encoding="utf-8")
        with mock.patch.object(bank, "genlib", runtime), mock.patch.dict(sys.modules, {"aiprep.gen": runtime}):
            bank.load_common(self.root)
            for _ in range(2):
                spec = bank.load_items({"id": "i90"}, self.root)["gens"][0]
                self.assertEqual(loaded_hash, bank.generation_source(spec)["source_hashes"]["runtime"])
                self.assertNotEqual(bank._source_hash(path), loaded_hash)
                self.assertEqual("blank", runtime.run(spec, 4)["kind"])
        refreshed = gen._exec(str(path), "provenance_runtime_new")
        self.assertNotEqual(loaded_hash, refreshed.RUNTIME_SOURCE_HASH)
        path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
        self.assertEqual(refreshed.RUNTIME_SOURCE_HASH, gen._exec(str(path), "provenance_runtime_crlf").RUNTIME_SOURCE_HASH)

    def test_common_registered_wrapper_hash_tracks_the_function_actually_called(self):
        path = Path(self.root) / "items/common/gens.py"
        source = path.read_text(encoding="utf-8")
        path.write_text(source + '\nfrom functools import partial\nbase("batches")(partial(batches))\n', encoding="utf-8")
        bank.load_common(self.root)
        self.assertFalse(hasattr(gen.bases()["batches"], "__code__"))
        spec = bank.load_items({"id": "i90"}, self.root)["gens"][1]
        item = gen.run(spec, 15)
        item["_generation"] = bank.generation_source(spec)
        first = collection.question(item, card=spec.id)
        self.assertEqual(bank._source_hash(path), first["content"]["generation"]["source_hashes"]["common"])
        path.write_text(source + '\nfrom functools import partial\ndef replacement(r, ranges):\n'
                        '    item = batches(r, ranges)\n    item["stem"] += " 새 표시 조건"\n    return item\n'
                        'base("batches")(partial(replacement))\n', encoding="utf-8")
        bank.load_common(self.root)
        changed = gen.run(spec, 15)
        changed["_generation"] = bank.generation_source(spec)
        after = collection.question(changed, card=spec.id)
        self.assertTrue(changed["stem"].endswith(" 새 표시 조건"))
        self.assertEqual(bank._source_hash(path), after["content"]["generation"]["source_hashes"]["common"])
        self.assertNotEqual(first["content"]["generation"]["version_hash"], after["content"]["generation"]["version_hash"])
        self.assertEqual(first, collection.question(item, card=spec.id))

    def test_bad_declarations_are_bank_errors_before_a_question_is_shown(self):
        path = Path(self.root) / "items/i90/gens.py"
        source = path.read_text(encoding="utf-8")
        cases = [("template_revision", value) for value in (2, True, [], "bad revision")]
        cases += [("template_id", "bad template"), ("display_params", "w"),
                  ("display_params", ["w", "w"]), ("display_params", ["missing"]),
                  ("display_params", [["w"]])]
        cases += [("display_params", [name]) for name in sorted(generation.RESERVED_PARAMS)]
        for key, value in cases:
            path.write_text(source + "\none_step.gen_spec.meta[%r] = %r\n" % (key, value), encoding="utf-8")
            with self.subTest(key=key, value=value), self.assertRaisesRegex(bank.AiBankError, "i90/i90-g01:.*" + key):
                bank.load_items({"id": "i90"}, self.root)
        # AiSession이 로드 오류를 차시 안내로 보관하고 나머지 초기화를 계속함.
        sess = self.session()
        self.assertIn("display_params", sess.errors["i90"])
        self.assertNotIn("i90-g01", sess.cards)

    def test_preflight_zero_division_is_a_bank_error_and_session_keeps_loading(self):
        self.declare_params(["w"])
        path = Path(self.root) / "items/i90/gens.py"
        path.write_text(path.read_text(encoding="utf-8") +
                        "\ndef divide_zero(r):\n    return 1 / 0\none_step.gen_spec.fn = divide_zero\n", encoding="utf-8")
        with self.assertRaisesRegex(bank.AiBankError, "i90/i90-g01: division by zero") as caught:
            bank.load_items({"id": "i90"}, self.root)
        self.assertIsInstance(caught.exception.__cause__, ZeroDivisionError)
        sess = self.session()
        self.assertIn("i90/i90-g01: division by zero", sess.errors["i90"])
        self.assertNotIn("i90-g01", sess.cards)

    def test_tuple_params_use_json_arrays_and_reach_model_input_without_mutating_item(self):
        path = Path(self.root) / "items/i90/gens.py"
        source = path.read_text(encoding="utf-8").replace('"lr": lr}', '"lr": lr, "point": (w, g)}')
        path.write_text(source, encoding="utf-8")
        self.declare_params(("point",))
        sess = self.session()
        self.assertNotIn("i90", sess.errors)
        sess.collection.set_enabled(True)
        practice = self.practice(sess)
        current = practice.current()
        raw = practice.queue[0]["view"]["item"]
        original = copy.deepcopy(raw)
        value = practice._collection_item(practice.queue[0])["content"]
        self.assertIsInstance(raw["params"]["point"], tuple)
        self.assertEqual(list(raw["params"]["point"]), value["generation"]["params"]["point"])
        self.assertEqual(value["generation"], generation.from_item(json.loads(collection.packed(value))))
        practice.answer(self.right(practice, current), 1, False)
        rows = dataset.prepare(sess.collection.snapshot())
        vocabulary = {"questions": ["<PAD>", "<UNK>"], "concepts": ["<PAD>", "<UNK>"]}
        self.assertEqual([value["generation"]], input_example.batch(rows, vocabulary)["question_provenance"]["query"])
        self.assertEqual(original, raw)

    def test_live_collection_transport_export_batch_and_withdrawal(self):
        self.declare_params(["w", "g", "lr"])
        sess = self.session()
        wire = test_learning_privacy.PrivacyTest()
        wire.setUp()
        self.addCleanup(wire.doCleanups)
        wire.app = app.application(wire.db)
        wire.collections["ai"] = sess.collection
        wire.consent = privacy.Consent(wire.collections, "https://example.test")
        wire.consent.choose(False)
        practice = self.practice(sess, "before")
        practice.current()
        self.assertFalse(Path(sess.collection.path).exists())
        wire.consent.choose(True)
        receipt = wire.consent.path.read_bytes()
        for name in ("first", "second"):
            practice = self.practice(sess, name)
            current = practice.current()
            practice.current()
            practice.answer(self.right(practice, current), 2, False)
        raw = sess.collection.snapshot()
        saved = copy.deepcopy(raw)
        generated = [row for row in raw if (row.get("item") or {}).get("generation")]
        self.assertEqual(4, len(generated))
        self.assertEqual({row["item_revision"] for row in generated}, {generated[0]["item_revision"]})
        self.assertEqual({"w", "g", "lr"}, set(generated[0]["item"]["generation"]["params"]))
        self.assertFalse(any("response" in row["data"] for row in raw[1:]))
        self.assertNotIn("explain", collection.packed([row["item"] for row in generated]))
        self.assertNotIn("answer", collection.packed([row["item"] for row in generated]))
        self.assertFalse(wire.consent.synchronize()["errors"])
        self.assertEqual(0, wire.consent.synchronize()["sent"])
        self.assertEqual(receipt, wire.consent.path.read_bytes())
        target = Path(self.tmp) / "server-export.jsonl"
        wire.db.export(str(target))
        exported = [json.loads(line) for line in target.read_text(encoding="utf-8").splitlines()]
        received = {row["event_id"]: row for row in exported if row.get("item")}
        for row in generated:
            self.assertEqual(row["item"], received[row["event_id"]]["item"])
        records = dataset.prepare(exported)
        self.assertEqual(2, len(records))
        self.assertEqual(generated[0]["item"]["generation"], records[0]["generation"])
        vocabulary = {"questions": ["<PAD>", "<UNK>"], "concepts": ["<PAD>", "<UNK>", "경사하강"]}
        batch = input_example.batch(records, vocabulary, 3)
        self.assertEqual([row["generation"] for row in records], batch["question_provenance"]["query"])
        self.assertEqual([None] * 3, batch["question_provenance"]["history"][0])
        self.assertEqual(records[0]["generation"], batch["question_provenance"]["history"][1][0])
        self.assertEqual(saved[1:], sess.collection.snapshot()[1:])
        profile = Path(sess.record.path).read_bytes()
        wire.consent.withdraw()
        self.assertTrue(wire.consent.synchronize()["withdrawn"])
        self.assertFalse(sess.collection.emit("answer", {"result": "pass"}))
        self.assertEqual(profile, Path(sess.record.path).read_bytes())
        with wire.db.connect() as db:
            self.assertEqual(0, db.execute("SELECT count(*) FROM events").fetchone()[0])

    def test_source_and_display_snapshot_survive_restore_and_old_cached_items_stay_unknown(self):
        self.declare_params(["w", "g", "lr"])
        sess = self.session()
        practice = self.practice(sess)
        practice.current()
        first = practice._collection_item(practice.queue[0])
        expected = first["content"]["generation"]
        spec = sess.cards["i90-g01"]["gen"]
        spec.meta["display_params"].append("answer")
        spec.meta["template_revision"] = "next-version"
        snapshot = bank.generation_source(spec)
        self.assertEqual(["w", "g", "lr"], snapshot["display_params"])
        self.assertEqual("one-step-1", snapshot["template_revision"])
        snapshot["display_params"].clear()
        self.assertEqual(first, practice._collection_item(practice.queue[0]))
        path = Path(self.root) / "items/i90/gens.py"
        path.write_text(path.read_text(encoding="utf-8") + "\n# 다음 파일 버전임\n", encoding="utf-8")
        # 디스크 수정만으로 이미 로드한 함수의 소스 해시를 바꾸지 않음.
        following = self.practice(sess, "following")
        following.current()
        self.assertEqual(expected, following._collection_item(following.queue[0])["content"]["generation"])
        restored = service.PracticeSet.restore(sess, practice.snapshot())
        self.assertEqual(first, restored._collection_item(restored.queue[0]))
        legacy = practice.snapshot()
        legacy["queue"][0]["view"]["item"].pop("_generation")
        old = service.PracticeSet.restore(sess, legacy)
        old.current()
        self.assertNotIn("generation", old._collection_item(old.queue[0])["content"])
        self.assertNotIn("_generation", old.queue[0]["view"]["item"])
        newest = self.practice(self.session(), "newest")
        newest.current()
        self.assertNotEqual(expected["version_hash"], newest._collection_item(newest.queue[0])["content"]["generation"]["version_hash"])

    def test_lf_and_crlf_share_source_version_and_instance_hashes(self):
        self.declare_params(["w", "g", "lr"])
        bank.load_common(self.root)
        original = bank.load_items({"id": "i90"}, self.root)["gens"]
        before = []
        for spec in original:
            item = gen.run(spec, 15)
            item["_generation"] = bank.generation_source(spec)
            before.append(collection.question(item, card=spec.id)["content"]["generation"])
        for folder in ("i90", "common"):
            path = Path(self.root) / "items" / folder / "gens.py"
            path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
        bank.load_common(self.root)
        after = bank.load_items({"id": "i90"}, self.root)["gens"]
        for expected, spec in zip(before, after):
            item = gen.run(spec, 15)
            item["_generation"] = bank.generation_source(spec)
            self.assertEqual(expected, collection.question(item, card=spec.id)["content"]["generation"])
        common = Path(self.root) / "items/common/gens.py"
        common.write_text(common.read_text(encoding="utf-8") + "\n# 공용 소스의 새 버전임\n", encoding="utf-8")
        bank.load_common(self.root)
        # register가 실제 실행할 공용 함수가 바뀌면 기존 spec에도 그 소스 해시를 붙임.
        current = bank.generation_source(original[1])
        self.assertNotEqual(before[1]["source_hashes"]["common"], current["source_hashes"]["common"])
        self.assertNotEqual(before[1]["version_hash"], current["version_hash"])

    def test_undeclared_params_are_omitted_and_display_identity_excludes_grading(self):
        sess = self.session()
        practice = self.practice(sess)
        practice.current()
        item = copy.deepcopy(practice.queue[0]["view"]["item"])
        item["params"]["answer"] = "HIDDEN-ANSWER"
        first = collection.question(item, card="i90-g01")
        value = first["content"]["generation"]
        self.assertEqual(("undeclared", {}), (value["params_status"], value["params"]))
        self.assertNotIn("HIDDEN-ANSWER", collection.packed(first["content"]))
        item["blanks"][0]["answer"] = ["HIDDEN-ANSWER"]
        item["explain"] = "HIDDEN-EXPLANATION"
        other = collection.question(item, card="i90-g01")
        self.assertNotEqual(first["revision"], other["revision"])
        self.assertEqual(value["instance_id"], other["content"]["generation"]["instance_id"])
        item["stem"] += " 조건 추가"
        self.assertNotEqual(value["instance_id"], collection.question(item, card="i90-g01")["content"]["generation"]["instance_id"])
        item["seed"] += 1
        self.assertNotEqual(value["instance_id"], collection.question(item, card="i90-g01")["content"]["generation"]["instance_id"])

    def test_option_order_is_observed_but_grading_flags_are_not(self):
        practice = self.practice(self.session(), card="i90-g02")
        current = practice.current()
        first = practice._collection_item(practice.queue[0])["content"]
        self.assertEqual(current["options"], first["options"])
        item = copy.deepcopy(practice.queue[0]["view"]["item"])
        order = list(reversed(practice.queue[0]["view"]["order"]))
        changed = collection.question(item, card="i90-g02", option_order=order)["content"]
        self.assertNotEqual(first["generation"]["instance_id"], changed["generation"]["instance_id"])
        for option in item["options"]:
            option.update(ok=not option["ok"], why="HIDDEN-GRADING")
        other = collection.question(item, card="i90-g02", option_order=order)["content"]
        self.assertEqual(changed, other)

    def test_params_declaration_rejects_unknown_reserved_and_unsafe_values(self):
        sess = self.session()
        practice = self.practice(sess)
        practice.current()
        original = practice.queue[0]["view"]["item"]
        for names, params in ((["unknown"], {}), (["answer"], {"answer": "hidden"}),
                              (["x"], {"x": {"nested": "hidden"}}), (["x"], {"x": float("nan")}),
                              (["x"], {"x": float("inf")}), (["x"], {"x": "a" * 129}),
                              (["x"], {"x": 2 ** 53}), ("x", {"x": 1})):
            with self.subTest(names=names, params=params), self.assertRaises(ValueError):
                item = copy.deepcopy(original)
                item["_generation"]["display_params"] = names
                item["params"] = params
                collection.question(item, card="i90-g01")
        item = copy.deepcopy(original)
        item["_generation"]["display_params"] = ["point", "translation", "direction"]
        item["params"] = {"point": [-4, 2], "translation": [3, -1], "direction": "destination_to_source",
                          "answer": [99, 99]}
        value = collection.question(item, card="i90-g01")["content"]["generation"]
        self.assertEqual({"point", "translation", "direction"}, set(value["params"]))
        for key in generation.RESERVED_PARAMS:
            item = copy.deepcopy(original)
            item["_generation"]["display_params"] = [key.upper()]
            item["params"] = {key.upper(): "hidden"}
            with self.subTest(key=key), self.assertRaises(ValueError):
                collection.question(item, card="i90-g01")
        item = copy.deepcopy(original)
        item["_generation"]["unknown"] = "hidden"
        with self.assertRaises(ValueError):
            collection.question(item, card="i90-g01")

    def test_server_rejects_invalid_new_fields_atomically_and_accepts_old_items(self):
        self.declare_params(["w", "g", "lr"])
        sess = self.session()
        practice = self.practice(sess)
        practice.current()
        item = practice._collection_item(practice.queue[0])
        server = test_learning_server.ServerTest()
        server.setUp()
        self.addCleanup(server.doCleanups)
        original = server.row(2)
        original.update(item=item["content"], item_revision=item["revision"])
        old = server.row(1)
        for key, value in (("extra", "hidden"), ("seed", True), ("params", {"answer": "hidden"}),
                           ("source_hashes", {}), ("instance_id", "f" * 64), ("template_revision", [])):
            changed = copy.deepcopy(original)
            changed["item"]["generation"][key] = value
            with self.subTest(key=key):
                status, _ = server.call("/v1/events", server.packet([old, changed]), server.token)
                self.assertEqual(400, status)
                self.assertEqual(0, server.count())
        for _ in range(2):
            self.assertEqual(200, server.call("/v1/events", server.packet([old, original]), server.token)[0])
        self.assertEqual(2, server.count())

    def test_dataset_uses_only_pre_prediction_return_and_preserves_legacy_rows(self):
        sess = self.session()
        sess.collection.set_enabled(True)
        practice = self.practice(sess)
        current = practice.current()
        practice.answer(self.right(practice, current), 1, False)
        events = sess.collection.snapshot()
        raw = copy.deepcopy(events)
        expected = dataset.prepare(events)[0]
        for mode in ("answer_only", "mismatch", "duplicate", "reconsent", "earlier_prediction", "old"):
            rows = copy.deepcopy(events)
            shown = next(row for row in rows if row["kind"] == "question_returned")
            answer = next(row for row in rows if row["kind"] == "answer")
            if mode == "answer_only":
                rows.remove(shown)
            elif mode == "mismatch":
                shown["item"]["generation"]["seed"] += 1
                shown["item"]["seed"] += 1
                shown["item"]["generation"]["instance_id"] = generation.instance_id(shown["item"]["generation"], shown["item"])
            elif mode in ("duplicate", "reconsent"):
                extra = copy.deepcopy(shown)
                extra.update(event_id=str(uuid.uuid4()), sequence=shown["sequence"] + 1,
                             kind="consent" if mode == "reconsent" else shown["kind"])
                answer["sequence"] += 1
                rows.insert(rows.index(answer), extra)
            elif mode == "earlier_prediction":
                answer["data"]["prediction_at"] = "2020-01-01T00:00:00+00:00"
            else:
                for row in (shown, answer):
                    row["item"].pop("generation")
            with self.subTest(mode=mode):
                self.assertIsNone(dataset.prepare(rows)[0]["generation"])
        changed = copy.deepcopy(events)
        answer = next(row for row in changed if row["kind"] == "answer")
        answer["data"].update(result="wrong", response="HIDDEN-RESPONSE", explain="HIDDEN-EXPLANATION")
        actual = dataset.prepare(changed)[0]
        self.assertEqual(expected["generation"], actual["generation"])
        self.assertEqual(expected["features"], actual["features"])
        self.assertNotIn("HIDDEN", collection.packed(actual))
        vocabulary = {"questions": ["<PAD>", "<UNK>"], "concepts": ["<PAD>", "<UNK>"]}
        before, after = (input_example.batch([row], vocabulary) for row in (expected, actual))
        self.assertEqual(before["inputs"], after["inputs"])
        self.assertEqual(before["question_provenance"], after["question_provenance"])
        self.assertEqual(raw, events)

    def test_version_six_bundle_and_sample_keep_generation_without_a_new_content_dependency(self):
        sess = self.session()
        practice = self.practice(sess)
        practice.current()
        item = practice._collection_item(practice.queue[0])
        events = []
        for n, row in enumerate(dataset.synthetic_events()[:6]):
            row.update(sequence=n * 2 + 2, item=item["content"], item_revision=item["revision"])
            row["data"].update(card="i90-g01", position=0)
            shown = copy.deepcopy(row)
            shown.update(sequence=n * 2 + 1, event_id=str(uuid.uuid4()), kind="question_returned")
            shown["data"].pop("result")
            events.extend([shown, row])
        root = Path(self.tmp) / "prepared"
        starter.write_starter(events, root)
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(6, manifest["features_version"])
        rows, vocabulary = input_example.load(root, "ai", "train")
        self.assertTrue(all(row["generation"] == item["content"]["generation"] for row in rows))
        destination = Path(self.tmp) / "sample.json"
        sample.write_sample(root, "ai", "train", 2, 42, 3, destination)
        saved = json.loads(destination.read_text(encoding="utf-8"))
        self.assertTrue(all(value == item["content"]["generation"] for value in saved["batch"]["question_provenance"]["query"]))
        self.assertTrue(all(starter.question_token(row) in vocabulary["questions"] for row in rows))

    def test_version_five_bundle_has_unknown_generation_without_backfill(self):
        root = Path(self.tmp) / "legacy"
        starter.write_starter(dataset.synthetic_events(), root)
        manifest = json.loads((root / "manifest.json").read_bytes())
        records = json.loads((root / "records/manifest.json").read_bytes())
        for name, info in records["files"].items():
            path = root / "records" / name
            rows = [json.loads(line) for line in path.read_bytes().splitlines()]
            for row in rows:
                row.pop("generation")
                for past in row["features"]["sequence_history"]:
                    past.pop("generation")
            path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
            info["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        records["features_version"] = 5
        (root / "records/manifest.json").write_text(json.dumps(records), encoding="utf-8")
        manifest["features_version"] = 5
        manifest["records_manifest_sha256"] = hashlib.sha256((root / "records/manifest.json").read_bytes()).hexdigest()
        (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        before = (root / "manifest.json").read_bytes()
        output = Path(self.tmp) / "legacy-sample.json"
        sample.write_sample(root, "ai", "train", 2, 42, 3, output)
        saved = json.loads(output.read_bytes())
        self.assertEqual(5, saved["features_version"])
        self.assertEqual({"query": [None, None], "history": [[None] * 3] * 2}, saved["batch"]["question_provenance"])
        self.assertEqual(before, (root / "manifest.json").read_bytes())
