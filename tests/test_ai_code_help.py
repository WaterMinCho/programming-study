# -*- coding: utf-8 -*-
"""코드 설명의 공개 참조와 번호·제목 일치, 기록 없는 읽기를 확인함."""
import copy
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

from aiprep import bank, service


FIXTURE = Path(__file__).parent / "ai_bank"
ROOT = Path(__file__).resolve().parents[1] / "ai"


def sample():
    return {"title": "학습 루프", "explanation": "기울기를 비운 뒤 역전파하고 가중치를 갱신합니다.",
            "reference": {"course": "intro", "lesson": "l90", "unit": "90a", "step": 3,
                          "title": "학습 루프의 세 줄"}}


class CodeHelpTest(unittest.TestCase):
    def test_verify_ai_reports_invalid_code_help_references(self):
        from tools import verify_ai
        note = {"id": "l90", "dir": str(FIXTURE / "learn/l90"), "markdown": "", "order": ["90a"], "unit_meta": {},
                "units": {"90a": {"lead": "", "steps": [
                    {"no": n, "scope": "memo" if n == 4 else "main", "facts": ["F1"], "blocks": []}
                    for n in range(1, 5)]}}}
        for change in ({}, {"course": "applied"}, {"step": 999}, {"title": "바뀐 제목"}, {"unit": "90i"}):
            with self.subTest(change=change):
                block = dict(sample(), kind="code-help")
                block["reference"] = dict(block["reference"], **change)
                note["units"]["90a"]["steps"][1]["blocks"] = [block]
                verifier = verify_ai.Verifier(None, io.StringIO())
                verify_ai.check_note_blocks(verifier, verify_ai.Lesson({"id": "i90"}, note, None, []))
                if change:
                    self.assertTrue(any(number == 8 and "코드 설명 참조" in message
                                        for _, number, message in verifier.failures), verifier.failures)
                else:
                    self.assertEqual([], verifier.failures)

    def test_schema_requires_explanation_and_exact_reference_but_code_is_optional(self):
        data = sample()
        for with_code in (False, True):
            if with_code:
                data["code"] = "optimizer.zero_grad()"
            blocks = bank.parse_blocks(["```ai-code-help", json.dumps(data), "```"])
            self.assertEqual([dict(data, kind="code-help")], blocks)
        invalid = [dict(data, reference=None), dict(data, explanation=""), dict(data, extra="unknown"),
                   dict(data, code=12), dict(data, title="두\n줄"), {k: v for k, v in data.items() if k != "reference"}]
        for change in ({"step": True}, {"step": 0}, {"step": "3"}, {"title": ""},
                       {"course": "app"}, {"lesson": "i90"}, {"lesson": "../l90"}, {"unit": "90a/3"},
                       {"section": ""}, {"section": "두\n줄"}):
            invalid.append(dict(data, reference=dict(data["reference"], **change)))
        for row in invalid:
            with self.subTest(row=row):
                self.assertIn("error", bank._code_help_block(json.dumps(row)))

    def test_hidden_deleted_reordered_and_renamed_steps_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "bank"
            shutil.copytree(FIXTURE, root)
            ref = sample()["reference"]
            self.assertEqual("i90", bank.resolve_code_reference(ref, root)["lesson"])
            for change in ({"course": "applied"}, {"lesson": "al90"}, {"step": 2},
                           {"step": 999}, {"title": "학습 루프의 세 줄 "}, {"unit": "90i"}, {"section": "없는 설명"}):
                with self.subTest(change=change), self.assertRaises(bank.AiBankError):
                    bank.resolve_code_reference(dict(ref, **change), root)
            page = root / "learn/l90/page.md"
            original = page.read_text(encoding="utf-8")
            for changed in (original.replace("### 학습 루프의 세 줄", "### 바뀐 설명"),
                            original.replace("### 학습 루프의 세 줄", "### 새 단계\n\n### 학습 루프의 세 줄"),
                            original.replace("### 학습 루프의 세 줄", "학습 루프의 세 줄")):
                page.write_text(changed, encoding="utf-8")
                with self.assertRaises(bank.AiBankError):
                    bank.resolve_code_reference(ref, root)
            page.write_text(original, encoding="utf-8")
            meta_path = root / "learn/l90/meta.json"
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            meta["units"] = {"90b": {}}
            meta_path.write_text(json.dumps(meta), encoding="utf-8")
            with self.assertRaises(bank.AiBankError):
                bank.resolve_code_reference(ref, root)

    def test_public_reader_does_not_construct_a_session_or_write_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "bank"
            shutil.copytree(FIXTURE, root)
            before = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}
            with mock.patch.object(service.AiSession, "__init__", side_effect=AssertionError("학습자 세션 생성")), \
                    mock.patch.object(service.collection, "Collection", side_effect=AssertionError("수집부 생성")), \
                    mock.patch.object(service.study, "write_text", side_effect=AssertionError("기록 쓰기")):
                data = service.read_note_reference(sample()["reference"], root)
                note = bank.load_note({"id": "l90"}, root)
                ref = dict(sample()["reference"], step=1, title=note["units"]["90a"]["steps"][0]["title"])
                guess = service.read_note_reference(ref, root)
            self.assertEqual("학습 루프의 세 줄", data["step"]["title"])
            self.assertNotIn("answers", guess)
            self.assertFalse(any(b["kind"] in {"guess", "reveal", "recall", "why", "rotate", "memo", "levels"}
                                 for s in (data["step"], guess["step"]) for b in s["blocks"]))
            self.assertEqual(before, {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()})

    def test_reference_does_not_return_questions_answers_or_source_markdown(self):
        ref = sample()["reference"]
        data = bank.resolve_code_reference(ref, FIXTURE)
        data["step"] = dict(data["step"], blocks=[
            {"kind": "text", "markdown": "입력과 출력의 모양을 비교합니다."},
            {"kind": "formula", "q": "수식의 확인 물음", "a": "답을 미리 펼치지 않음"},
            *({"kind": kind, "answer": "답을 미리 펼치지 않음"} for kind in
              ("guess", "reveal", "recall", "why", "rotate", "memo", "levels"))])
        with mock.patch.object(bank, "resolve_code_reference", return_value=data):
            result = service.read_note_reference(ref, FIXTURE)
        self.assertEqual([{"kind": "text", "markdown": "입력과 출력의 모양을 비교합니다."}], result["step"]["blocks"])
        self.assertNotIn("답을 미리", json.dumps(result, ensure_ascii=False))
        self.assertNotIn("수식의 확인 물음", json.dumps(result, ensure_ascii=False))
        self.assertNotIn("markdown", result["step"])

    def test_published_code_help_references_match_exact_visible_steps(self):
        found = []
        for entry in bank.read_index(ROOT)["lessons"]:
            if not bank.is_ready(entry, ROOT):
                continue
            note = bank.load_note({"id": entry["page"], "title": entry["title"]}, ROOT)
            for key in note["visible"]:
                for step in note["units"][key]["steps"]:
                    for block in step["blocks"]:
                        if block["kind"] != "code-help":
                            continue
                        with self.subTest(page=entry["page"], unit=key, step=step["no"]):
                            self.assertNotIn("error", block)
                            original = copy.deepcopy(block)
                            data = service.read_note_reference(block["reference"], ROOT)
                            self.assertEqual(block["reference"]["title"], data["step"]["title"])
                            self.assertEqual(original, block)
                            found.append((entry["course"], block["reference"]["course"]))
        self.assertIn(("intro", "intro"), found)
        self.assertIn(("app", "intro"), found)
        self.assertIn(("app", "applied"), found)
