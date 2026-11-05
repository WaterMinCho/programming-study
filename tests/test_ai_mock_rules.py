# -*- coding: utf-8 -*-
"""실제 회차의 배분·근거·중복 경계와 작은 검증 회차의 호환을 임시 은행에서 확인함."""
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest

from tests import aifix
from tools import ai_mock_rules as rules
from tools import verify_ai


TABLE = {
    "m1": [1, 2, 2, 4, 2, 2, 2, 3, 2, 4, 3, 3, 0, 0, 0, 0, 0],
    "m2": [1, 2, 2, 3, 2, 2, 1, 2, 2, 2, 2, 2, 2, 2, 1, 2, 0],
    "m3": [2, 1, 2, 2, 2, 2, 2, 2, 1, 2, 2, 1, 2, 2, 2, 2, 1],
}
FENCE = "\x60" * 3
NAMES = ["--writer", "출제", "--resolver", "풀이", "--checker", "대조", "--reviewer", "검토"]


def exam(mid="m1"):
    counts = {"i%02d" % n: count for n, count in enumerate(TABLE[mid], 1) if count}
    entry = {"id": mid, "title": "모의고사", "count": 30, "minutes": 60,
             "range": [1, 12 if mid == "m1" else 17], "window": ["2026-11-14", "2026-11-16"]}
    meta = dict(entry, format=1, blueprint=counts)
    items, local = [], {}
    lessons = [lesson for lesson, count in counts.items() for _ in range(count)]
    for pos, lesson in enumerate(lessons):
        local[lesson] = local.get(lesson, 0) + 1
        fact = "F%s-%02d" % (lesson[1:], (int(mid[1:]) - 1) * 10 + local[lesson])
        marker = "%s_case_%d" % (mid, pos)
        item = {"id": "%s-%02d" % (mid, pos + 1), "lesson": lesson, "unit": "%da" % int(lesson[1:]),
                "step": "%da/1" % int(lesson[1:]), "facts": [fact], "ref": ["%d차시 슬 p1" % int(lesson[1:])],
                "level": 1 if pos < 8 else 2 if pos < 23 else 3, "topic": "개념_%s" % marker,
                "assignment": pos < 5, "explain": "주어진 입력과 연산을 대조해 각 보기의 조건을 판단합니다."}
        prefix = "%s azure%d coral%d silver%d" % (marker, pos, pos, pos)
        if pos < 14:
            if pos < 6:
                mode, answer = "code", "forward"
                stem = prefix + "에서 실행할 함수를 빈칸에 적으세요.\n\n" + FENCE + "python\nmethod_%s = ____\n" % marker + FENCE
            elif pos < 11:
                mode, answer, stem = "number", "2", prefix + "에서 1 + 1은 ____입니다."
            else:
                mode, answer, stem = "word", "기울기", prefix + "에서 변화량의 비율을 ____라고 부릅니다."
            item.update(kind="blank", stem=stem, blanks=[{"mode": mode, "answer": [answer]}])
        else:
            multi = pos >= 27
            pick = "right" if pos < 21 or multi else "wrong"
            oks = [True, True, False, False] if multi else [True, False, False, False] if pick == "right" else [True, True, True, False]
            stem = prefix + ("에서 옳은 것을 모두 고르세요." if multi else "에서 옳은 것을 고르세요." if pick == "right" else "에서 옳지 않은 것을 고르세요.")
            options = [{"text": "%s 선택 %s" % (marker, name), "ok": ok, "why": "주어진 조건으로 판단합니다.",
                        "aim": "조건을 다르게 읽음"} for name, ok in zip(("가", "나", "다", "라"), oks)]
            item.update(kind="choice", stem=stem, pick=pick, multi=multi, options=options)
        if pos < 3:
            item["pattern"] = "S90"
        items.append(item)
    return entry, meta, items


class RuleTest(unittest.TestCase):
    def problems(self, mid="m1", edit=None):
        entry, meta, items = exam(mid)
        if edit:
            edit(entry, meta, items)
        return rules.exam_problems(mid, entry, meta, items, {"S90"})

    def test_three_tables_and_exact_totals(self):
        for mid in TABLE:
            with self.subTest(mid=mid):
                self.assertEqual(30, sum(TABLE[mid]))
                self.assertEqual(tuple(TABLE[mid]), rules.LESSON_COUNTS[mid])
                self.assertEqual([], self.problems(mid))

    def test_blueprint_is_not_trusted_instead_of_actual_counts(self):
        def edit(entry, meta, items):
            items[0]["lesson"] = "i02"
            meta["blueprint"]["i01"] -= 1
            meta["blueprint"]["i02"] += 1
        problems = self.problems(edit=edit)
        self.assertTrue(any("blueprint" in text for text in problems))
        self.assertTrue(any("차시별 문항 수" in text for text in problems))

    def test_lesson_boundaries_and_second_exam_zero_row(self):
        for mid, lesson in (("m1", "i13"), ("m2", "i17"), ("m3", "i18")):
            with self.subTest(mid=mid):
                self.assertTrue(any("차시별" in text for text in self.problems(
                    mid, lambda e, m, rows: rows[0].update(lesson=lesson))))
        self.assertEqual([], self.problems("m2", lambda e, m, rows: m["blueprint"].update(i17=0)))

    def test_minutes_count_range_and_boolean_are_checked(self):
        for place, key, value in (("entry", "minutes", 59), ("meta", "count", 29), ("meta", "count", True),
                                  ("meta", "format", True), ("entry", "range", [1, 17])):
            with self.subTest(key=key, value=value):
                def edit(entry, meta, items):
                    (entry if place == "entry" else meta)[key] = value
                self.assertTrue(self.problems(edit=edit))

    def test_blank_categories_are_exclusive(self):
        def category(*blanks):
            return rules.blank_category({"blanks": list(blanks)})
        code = {"mode": "code", "answer": ["forward"]}
        number = {"mode": "number", "answer": ["2"]}
        word = {"mode": "word", "answer": ["기울기"]}
        self.assertEqual("code", category(code, code))
        self.assertEqual("value", category(code, number))
        self.assertEqual("word", category(code, word))
        for answer in ("2", "-1.5", "1/2", "[2, 3]", "(4, 1)", "2 ** 3", "1e-3", "torch.Size([2, 3])"):
            with self.subTest(answer=answer):
                self.assertEqual("value", category({"mode": "code", "answer": [answer]}))
        for answer in ("True", "False", "None", "float32", "step"):
            with self.subTest(answer=answer):
                self.assertEqual("code", category({"mode": "code", "answer": [answer]}))

    def test_code_value_and_word_quota_boundaries(self):
        for pos, mode, answer in ((0, "number", "2"), (6, "code", "step"), (6, "word", "분산")):
            with self.subTest(mode=mode):
                def edit(e, m, rows):
                    rows[pos]["blanks"] = [{"mode": mode, "answer": [answer]}]
                self.assertTrue(any("빈칸은 코드" in text for text in self.problems(edit=edit)))

    def test_kind_pick_and_level_totals(self):
        mutations = [
            lambda rows: rows[-1].update(pick="wrong", multi=False),
            lambda rows: rows[14].update(pick="wrong"),
            lambda rows: rows[0].update(level=2),
            lambda rows: rows[13].update(kind="choice", options=[], pick="right"),
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                self.assertTrue(self.problems(edit=lambda e, m, rows: mutation(rows)))

    def test_assignment_flags_require_code_blanks_and_five_items(self):
        self.assertTrue(any("5개 이상" in text for text in self.problems(
            edit=lambda e, m, rows: rows[0].update(assignment=False))))
        problems = self.problems(edit=lambda e, m, rows: rows[6].update(assignment=True))
        self.assertTrue(any("코드 울타리" in text for text in problems))
        self.assertTrue(any("bool" in text for text in self.problems(
            edit=lambda e, m, rows: rows[0].update(assignment="true"))))

    def test_pattern_presence_and_unknown_id(self):
        self.assertTrue(any("3개 이상" in text for text in self.problems(
            edit=lambda e, m, rows: rows[0].pop("pattern"))))
        self.assertTrue(any("존재하는 뼈대" in text for text in self.problems(
            edit=lambda e, m, rows: rows[0].update(pattern="S999"))))

    def test_topic_limit_normalizes_space_case_and_width(self):
        def edit(e, m, rows):
            for row, name in zip(rows, ("Batch Norm", "batchnorm", "ＢａｔｃｈＮｏｒｍ")):
                row["topic"] = name
        self.assertTrue(any("한 회에 3개" in text for text in self.problems(edit=edit)))
        self.assertEqual([], self.problems(edit=lambda e, m, rows: [row.update(topic="같은 개념") for row in rows[:2]]))

    def test_jaccard_includes_exact_three_fifths(self):
        left = rules.tokens("a b c d")
        self.assertTrue(rules.overlap(left, rules.tokens("a b c e")))
        self.assertFalse(rules.overlap(left, rules.tokens("a b e f")))
        self.assertFalse(rules.overlap(frozenset(), frozenset()))
        self.assertEqual(rules.tokens("ＦＯＯ 0.5 ____"), rules.tokens("foo 0.5"))
        self.assertTrue(rules.practice_problems([{"id": "m1-01", "stem": "a b c d"}], [("i01-b01", rules.tokens("a b c e"))]))

    def test_cross_exam_duplicate_ignores_answer_metadata_and_option_order(self):
        item = exam()[2][14]
        twin = copy.deepcopy(item)
        twin.update(id="m2-01", explain="다른 해설입니다.", facts=["another"])
        twin["options"].reverse()
        self.assertTrue(rules.cross_problems("m1", {"m1": [item], "m2": [twin]}))

    def test_fact_limit_counts_exams_instead_of_item_uses(self):
        exams = {mid: [{"id": "%s-%d" % (mid, n), "kind": "blank", "stem": "%s original %d" % (mid, n), "facts": ["F01-01"]}
                       for n in range(3)] for mid in ("m1", "m2", "m3")}
        self.assertEqual([], rules.cross_problems("m1", {key: exams[key] for key in ("m1", "m2")}))
        self.assertTrue(any("세 회 중 2회" in text for text in rules.cross_problems("m1", exams)))


class ValidationTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="mock_rules_")
        self.addCleanup(temporary.cleanup)
        self.bank = Path(temporary.name) / "bank"
        aifix.pc_bank(str(self.bank))
        index = self.read("index.json")
        index["lessons"] = []
        index["mocks"] = [exam(mid)[0] for mid in TABLE]
        for group in index["patterns"]:
            for unit in group["units"].values():
                unit["after"] = "i01"
        for n in range(1, 18):
            lid, pid, unit = "i%02d" % n, "l%02d" % n, "%da" % n
            index["lessons"].append({"id": lid, "no": n, "title": "검증 차시", "page": pid, "units": 1, "weight": 1})
            index["pages"].append({"id": pid, "title": "검증 차시"})
            index["order"].append(pid)
            fids = ["F%02d-%02d" % (n, fid) for fid in range(1, 31)] + ["F%02d-99" % n]
            self.write("learn/%s/meta.json" % pid, {"format": 1, "id": pid, "title": "검증 차시", "defines": [],
                "needs": [], "sections": {unit: "계산을 확인합니다"}, "units": {unit: {}}, "outputs": [], "sources": []})
            self.text("learn/%s/page.md" % pid, "# 검증 차시\n\n## 계산을 확인합니다\n\n### 값을 확인합니다\n\n<!-- facts: %s -->\n\n값을 계산합니다.\n" % " ".join(fids))
            self.write("items/%s/meta.json" % lid, {"format": 1, "id": lid, "no": n, "page": pid, "units": {unit: {}}})
            self.write("items/%s/work/facts.json" % lid, {"facts": [
                {"id": fid, "text": "검증할 개념을 기록함.", "verdict": "맞음", "where": ["%d차시 슬 p1" % n],
                 "from": "회귀 검사", "checked": "2026-11-05"} for fid in fids], "errata": []})
            self.write("items/%s/work/items.json" % lid, {"items": [
                {"id": lid + "-b01", "kind": "blank", "stem": "practice_%s isolated quartz rocket ____" % lid,
                 "blanks": [{"mode": "word", "answer": ["value"]}], "facts": ["F%02d-99" % n]}]})
        self.write("index.json", index)
        self.save_exam()

    def text(self, rel, text):
        path = self.bank / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def write(self, rel, value):
        self.text(rel, json.dumps(value, ensure_ascii=False, indent=1) + "\n")

    def read(self, rel):
        return json.loads((self.bank / rel).read_text())

    def save_exam(self, mid="m1", edit=None):
        entry, meta, items = exam(mid)
        if edit:
            edit(entry, meta, items)
        self.write("mocks/%s/meta.json" % mid, meta)
        self.write("mocks/%s/work/items.json" % mid, {"format": 1, "items": items})
        return items

    def mutate_item(self, number, **fields):
        data = self.read("mocks/m1/work/items.json")
        data["items"][number].update(fields)
        self.write("mocks/m1/work/items.json", data)

    def verify(self, *arguments):
        output = io.StringIO()
        code = verify_ai.main(list(arguments or ("m1",)) + ["--bank", str(self.bank), "--seeds", "2"], output)
        return code, output.getvalue()

    def assert_failure(self, text, *arguments):
        code, output = self.verify(*(arguments or ("m1",)))
        self.assertEqual(1, code, output)
        self.assertIn(text, output)

    def set_fact(self, item_number, **changes):
        item = self.read("mocks/m1/work/items.json")["items"][item_number]
        path = "items/%s/work/facts.json" % item["lesson"]
        data = self.read(path)
        next(row for row in data["facts"] if row["id"] == item["facts"][0]).update(changes)
        self.write(path, data)

    def test_valid_real_exam(self):
        code, output = self.verify("m1")
        self.assertEqual(0, code, output)
        self.assertIn("OK: 묶음 1개 통과", output)

    def test_all_rounds_pass_with_distinct_questions_and_facts(self):
        for mid in ("m2", "m3"):
            self.save_exam(mid)
        code, output = self.verify("m1", "m2", "m3")
        self.assertEqual(0, code, output)
        self.assertIn("OK: 묶음 3개 통과", output)

    def test_two_and_three_blanks(self):
        stem = "두 함수를 지정합니다.\n\n%s python\nleft = ____\nright = ____\n%s" % (FENCE, FENCE)
        self.mutate_item(0, stem=stem, blanks=[{"mode": "code", "answer": ["forward"]}, {"mode": "code", "answer": ["step"]}])
        code, output = self.verify("m1")
        self.assertEqual(0, code, output)
        self.mutate_item(0, stem=stem.replace("right =", "third = ____\nright ="),
                         blanks=[{"mode": "code", "answer": [word]} for word in ("forward", "step", "detach")])
        self.assert_failure("빈칸 수는 1~2개")

    def test_multi_exactly_two_answers_and_four_options(self):
        items = self.read("mocks/m1/work/items.json")
        items["items"][27]["options"][2]["ok"] = True
        self.write("mocks/m1/work/items.json", items)
        self.assert_failure("답이 2개가 아닙니다")
        items["items"][27]["options"].pop()
        self.write("mocks/m1/work/items.json", items)
        self.assert_failure("보기는 4개")

    def test_unknown_fact_and_unrelated_step_facts(self):
        self.mutate_item(0, facts=["F17-01"])
        self.assert_failure("facts.json 에 없습니다")
        self.mutate_item(0, facts=["F01-01"], step="1a/2")
        self.assert_failure("step 1a/2가 없습니다")
        self.mutate_item(0, unit="1z", step="1z/1")
        self.assert_failure("실제 학습 단계")

    def test_existing_step_must_share_a_fact(self):
        path = self.bank / "learn/l01/page.md"
        path.write_text(path.read_text().replace("F01-01 ", ""))
        self.assert_failure("사실 줄과 겹치지 않습니다")

    def test_pattern_can_use_its_own_note_and_facts(self):
        self.mutate_item(0, unit="18a", step="18a/1", facts=["F18-02"])
        code, output = self.verify("m1")
        self.assertEqual(0, code, output)
        self.mutate_item(0, pattern="S404")
        self.assert_failure("존재하는 뼈대")

    def test_unknown_lesson_fails_without_loading_it(self):
        self.mutate_item(0, lesson="i21")
        self.assert_failure("lesson이 출제 범위")

    def test_first_ref_requires_matching_lecture_or_summary(self):
        self.mutate_item(0, ref=["PyTorch 문서 Linear"])
        self.assert_failure("첫 ref는 i01")
        self.mutate_item(0, ref=["요약 1주차 p1"])
        self.assertEqual(0, self.verify("m1")[0])

    def test_concept_only_number_shape_and_numeric_code(self):
        self.set_fact(0, concept_only=True)
        self.mutate_item(0, blanks=[{"mode": "code", "answer": ["2"]}])
        self.assert_failure("concept_only 사실")
        self.mutate_item(0, blanks=[{"mode": "shape", "answer": ["[2, 3]"]}])
        self.assert_failure("concept_only 사실")

    def test_concept_only_value_options(self):
        self.set_fact(14, concept_only=True)
        self.mutate_item(14, options=[{"text": str(n), "ok": n == 0, "why": "값을 비교합니다.", "aim": "값을 바꿈"} for n in range(4)])
        self.assert_failure("concept_only 사실")
        data = self.read("mocks/m1/work/items.json")
        data["items"][14]["options"][-1]["text"] = "계산할 수 없습니다."
        self.write("mocks/m1/work/items.json", data)
        self.assert_failure("concept_only 사실")

    def test_unverified_fact_and_missing_simplification_policy(self):
        self.set_fact(0, verdict="확인 못 함")
        self.assert_failure("확인 못 함")
        self.set_fact(0, verdict="단순화")
        self.assert_failure("ask_as 가 없습니다")
        self.set_fact(0, verdict="잘 모름")
        self.assert_failure("verdict를 모릅니다")

    def test_errata_cannot_be_hidden_by_omitting_item_flag(self):
        data = self.read("items/i01/work/items.json")
        data["items"][0].update(facts=["F01-01"], errata=["X01-01"])
        self.write("items/i01/work/items.json", data)
        self.assert_failure("정정 근거 사실 F01-01")

    def test_fact_errata_marker_is_excluded(self):
        self.set_fact(0, errata=["X01-01"])
        self.assert_failure("정정 근거 사실 F01-01")

    def test_malformed_answers_and_metadata_fail_without_crashing(self):
        cases = [({"blanks": [{"mode": "code", "answer": 2}]}, "answer 는 글 목록"),
                 ({"facts": [["F01-01"]]}, "facts는 비어 있지 않은 사실 ID 목록"),
                 ({"blanks": 2}, "blanks는 빈칸 객체 목록"),
                 ({"assignment": "yes"}, "assignment는 bool")]
        for fields, message in cases:
            with self.subTest(fields=fields):
                self.save_exam()
                self.mutate_item(0, **fields)
                self.assert_failure(message)
        self.save_exam()
        data = self.read("mocks/m1/work/items.json")
        data["items"][14]["options"][0]["text"] = 3
        self.write("mocks/m1/work/items.json", data)
        self.assert_failure("보기 text는 비어 있지 않은 글")

    def test_deep_limit(self):
        for n in range(2):
            self.mutate_item(n, deep=True)
        self.assertEqual(0, self.verify("m1")[0])
        self.mutate_item(2, deep=True)
        self.assert_failure("deep 문항은 2개 이하")

    def test_style_and_code_format_are_checked(self):
        self.mutate_item(0, explain="설명 \u2014 결과입니다.")
        self.assert_failure("em-dash")
        self.save_exam()
        self.mutate_item(0, stem="코드를 완성하세요.\n%s python\nfor = ____\n%s" % (FENCE, FENCE))
        self.assert_failure("코드 구문")
        self.mutate_item(0, stem="코드를 완성하세요.\n%s python\nx = ____" % FENCE)
        self.assert_failure("닫히지 않은 코드 울타리")

    def test_practice_static_alt_cloze_and_generator_are_compared(self):
        target = self.read("mocks/m1/work/items.json")["items"][0]["stem"]
        path = "items/i01/work/items.json"
        original = self.read(path)
        for field in ("stem", "alt"):
            data = copy.deepcopy(original)
            data["items"][0].update({field: target if field == "stem" else {"stem": target}})
            self.write(path, data)
            self.assert_failure("연습 지문 토큰 자카드")
        self.write(path, original)
        self.write("items/i01/work/statements.json", {"topics": [{"id": "t", "statements": [{"id": "s", "text": "statement",
                    "cloze": {"text": target}}]}]})
        self.assert_failure("연습 지문 토큰 자카드")
        self.write("items/i01/work/statements.json", {"topics": []})
        self.text("items/i01/gens.py", "from aiprep.gen import gen, blank\n@gen('i01-g01', unit='1a')\ndef make(r):\n"
                  "    return blank(stem=%r, blanks=[{'mode':'code','answer':['forward']}], explain='확인합니다.')\n" % target)
        self.assert_failure("i01-g01@")

    def test_selecting_one_exam_still_checks_other_rounds(self):
        _, meta, _ = exam("m2")
        twin = copy.deepcopy(self.read("mocks/m1/work/items.json")["items"][0])
        twin["id"] = "m2-01"
        self.write("mocks/m2/meta.json", meta)
        self.write("mocks/m2/work/items.json", {"items": [twin]})
        self.assert_failure("회차 간 같은 문항", "m1")

    def test_fact_reuse_across_three_rounds(self):
        for mid in ("m2", "m3"):
            self.save_exam(mid, lambda e, m, rows: rows[0].update(facts=["F01-01"]))
        self.assert_failure("세 회 중 2회 이하", "m1")

    def test_signature_requires_valid_rules_and_detects_changed_items(self):
        self.assert_failure("review.json", "m1", "--require-review")
        code, output = self.verify("m1", "--sign", *NAMES)
        self.assertEqual(0, code, output)
        self.assertEqual(0, self.verify("m1", "--require-review")[0])
        self.mutate_item(0, explain="다시 계산해 확인합니다.")
        self.assert_failure("검토 뒤에 바뀐 파일", "m1", "--require-review")

    def test_mock_answers_and_first_pass_are_graded(self):
        items = self.read("mocks/m1/work/items.json")["items"]
        answers = {}
        for item in items:
            if item["kind"] == "blank":
                answers[item["id"]] = [blank["answer"][0] for blank in item["blanks"]]
            else:
                order = verify_ai.ai_seal.option_order(item)
                selected = [n for n, option in enumerate(item["options"])
                            if option["ok"] == (item["pick"] == "right")]
                answers[item["id"]] = {"picked": [order.index(n) + 1 for n in selected]}
        self.write("first.json", answers)
        path = str(self.bank / "first.json")
        code, output = self.verify("m1", "--answers", path)
        self.assertEqual(0, code, output)
        self.assertIn("재풀이 대조: 맞음 30 / 30", output)
        answers[items[0]["id"]] = ["wrong"]
        self.write("first.json", answers)
        code, output = self.verify("m1", "--sign", *NAMES, "--first-pass", path, "--minutes", "42")
        self.assertEqual(0, code, output)
        first = self.read("mocks/m1/work/review.json")["first_pass"]
        self.assertEqual((30, 29, ["m1-01"], 42), (first["cards"], first["correct"], first["wrong"], first["minutes"]))
        code, output = self.verify("m1", "--sign", *NAMES, "--keep-first-pass")
        self.assertEqual(0, code, output)
        self.assertEqual(first, self.read("mocks/m1/work/review.json")["first_pass"])

    def test_failed_rules_do_not_write_signature(self):
        self.mutate_item(0, assignment=False)
        self.assert_failure("실패가 있어 서명하지 않았습니다", "m1", "--sign", *NAMES)
        self.assertFalse((self.bank / "mocks/m1/work/review.json").exists())

    def test_unreadable_first_pass_does_not_replace_previous_record(self):
        code, output = self.verify("m1", "--sign", *NAMES)
        self.assertEqual(0, code, output)
        review = self.read("mocks/m1/work/review.json")
        review["first_pass"] = {"cards": 30, "correct": 29, "wrong": ["m1-01"], "minutes": 42}
        self.write("mocks/m1/work/review.json", review)
        path = self.bank / "mocks/m1/work/review.json"
        before = path.read_bytes()
        self.assert_failure("답안을 읽을 수 없습니다", "m1", "--sign", *NAMES,
                            "--first-pass", str(self.bank / "missing.json"))
        self.assertEqual(before, path.read_bytes())

    def test_small_fixture_keeps_basic_validation(self):
        items = exam()[2][:4]
        for n, item in enumerate(items, 1):
            item["id"] = "m90-%02d" % n
            for key in ("topic", "assignment", "pattern", "level", "lesson", "facts", "ref", "unit", "step"):
                item.pop(key, None)
        self.write("mocks/m90/meta.json", {"id": "m90", "count": 4})
        self.write("mocks/m90/work/items.json", {"items": items})
        opts = verify_ai.parse_args([])
        verifier = verify_ai.Verifier(opts, io.StringIO())
        verify_ai.check_mock(verifier, str(self.bank), {"id": "m90", "title": "검증", "count": 4}, {})
        self.assertEqual([], verifier.failures)


if __name__ == "__main__":
    unittest.main()
