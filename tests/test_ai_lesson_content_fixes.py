"""본문 조건과 새 확인 물음의 기록 호환을 대조함. 모델은 불러오지 않음."""
import copy
import re
from fractions import Fraction
from pathlib import Path

from aiprep import bank, review
from tests.test_ai_service import Base

ROOT = Path(__file__).resolve().parents[1]


def note(lid):
    return bank.load_note({"id": lid}, str(ROOT / "ai"))


def aspect_blocks():
    return note("l15")["units"]["15b"]["steps"][2]["blocks"]


def old_aspect_note():
    """기존 블록 ID와 답 20의 저장·복원 조건을 재현함."""
    data = note("l15")
    levels = next(b for b in data["units"]["15b"]["steps"][2]["blocks"] if b["kind"] == "levels")
    levels["id"] = "15b-levels"
    for row in levels["levels"]:
        row["id"] = levels["id"]
    levels["levels"][0].update({"q": "가로와 세로의 수를 더하면 ____ 입니다.", "answer": ["20"]})
    return data


class LessonContentTest(Base):
    def test_versioned_level_preserves_previous_records_and_uses_new_answer(self):
        blocks = aspect_blocks()
        levels = next(b for b in blocks if b["kind"] == "levels")
        fresh = levels["levels"][0]
        self.assertEqual(("15b-levels-v2", 7, ["6"], "number"),
                         (fresh["id"], fresh["level"], fresh["answer"], fresh["mode"]))
        previous = old_aspect_note()
        old = next(b for b in previous["units"]["15b"]["steps"][2]["blocks"] if b["kind"] == "levels")["levels"][0]
        sess = self.session()
        sess.notes["i90"] = previous
        sess.save_recall("i90", "15b", old["id"], True, level=7, value="20", block=old)
        for step in previous["units"]["15b"]["steps"]:
            for block in step["blocks"]:
                if block["kind"] == "recall":
                    sess.save_recall("i90", "15b", block["id"], True, value=block["answer"][0], block=block)
        first = copy.deepcopy(sess.record.log)
        reopened = self.session()
        reopened.notes["i90"] = note("l15")
        self.assertEqual(first, reopened.record.log)
        self.assertFalse(reopened.check_recall(fresh, "20"))
        for value in ("6", "6.0", "12/2"):
            self.assertTrue(reopened.check_recall(fresh, value))
        reopened.save_recall("i90", "15b", fresh["id"], True, level=7, value="6", block=fresh)
        self.assertEqual(first, reopened.record.log[:len(first)])
        self.assertEqual(("15b-levels-v2", 7), (reopened.record.log[-1]["id"], reopened.record.log[-1].get("level")))
        self.assertEqual({}, review.card_events(reopened.record.log))

    def test_versioned_level_preserves_previous_read_and_practice_completion(self):
        current = note("l15")
        previous = old_aspect_note()
        sess = self.session()
        sess.notes["i90"] = previous
        sess.mark_read("i90", "15b")
        sess.save_step("i90", "15b", 3)
        sess._append({"kind": "set", "set": "previous-15b", "mode": "unit", "lesson": "i90", "unit": "15b"})
        sess._append({"kind": "set_end", "set": "previous-15b"})
        before = (sess._state().unit_stats("i90", "15b"), sess.completed_units(),
                  sess.unit_list("i90"), sess._local(), sess._card_versions())
        self.assertTrue(before[0]["read"])
        self.assertTrue(before[0]["practiced"])
        self.assertIn(("i90", "15b"), before[1])
        reopened = self.session()
        reopened.notes["i90"] = current
        after = (reopened._state().unit_stats("i90", "15b"), reopened.completed_units(),
                 reopened.unit_list("i90"), reopened._local(), reopened._card_versions())
        self.assertEqual(before, after)

    def test_mean_loss_example_and_counterexamples_use_different_denominators(self):
        text = (ROOT / "ai/learn/l10/page.md").read_text()
        self.assertIn("샘플 손실을 같은 비중으로 평균", text)
        self.assertIn("일부 샘플을 손실 계산에서 제외", text)
        size1, loss1 = map(int, re.search(r"샘플 (\d+)개의 평균 손실이 (\d+)이면", text).groups())
        size2, loss2 = map(int, re.search(r"마지막 샘플 (\d+)개의 손실이 (\d+)이면", text).groups())
        total, count = map(int, re.search(r"전체 평균 (\d+) ÷ (\d+)", text).groups())
        self.assertEqual(Fraction(total, count), Fraction(size1 * loss1 + size2 * loss2, size1 + size2))
        memo = next(b for step in note("l10")["units"]["10e"]["steps"]
                    for b in step["blocks"] if b["kind"] == "memo")["items"][0]
        self.assertIn("같은 비중", memo["q"])
        m1, m2, a1, a2 = map(int, re.findall(r"\d+", memo["q"]))
        self.assertIn(f"= {Fraction(m1 * a1 + m2 * a2, m1 + m2)}입니다.", memo["a"])
        weighted = (Fraction(1) + 1 + 8 * 3) / (1 + 1 + 8)
        self.assertEqual(Fraction(13, 5), weighted)
        self.assertNotEqual(Fraction(5, 3), weighted)
        self.assertEqual(2, (Fraction(1) + 3) / 2)

    def test_packed_length_matches_tokens_after_truncation_before_padding(self):
        text = (ROOT / "ai/learn/l17/page.md").read_text()
        self.assertIn("최대 길이로 자른 뒤 PAD를 붙이기 전", text)
        self.assertIn("현재 입력의 시간 축 길이 이하", text)
        original, maximum, stated = map(int, re.search(r"원래 길이가 (\d+)이고 최대 길이가 (\d+)라면 (\d+)를", text).groups())
        self.assertEqual(stated, min(original, maximum))
        ids = list(range(1, original + 1))[:maximum]
        length = len(ids)
        ids += [0] * (maximum - length)
        self.assertEqual((stated, maximum), (length, len(ids)))

    def test_uint8_explanation_uses_the_same_wrapped_value(self):
        blocks = note("al01")["units"]["a1c"]["steps"][2]["blocks"]
        why = next(b for b in blocks if b["kind"] == "why")
        self.assertIn("clip", why["q"])
        self.assertIn("NumPy의 +", why["q"])
        left, right = map(int, re.search(r"값 (\d+)과 (\d+)", why["q"]).groups())
        wrapped = int(re.search(r"더하면 (\d+)가", why["q"])[1])
        self.assertEqual(wrapped, (left + right) % 256)
        self.assertEqual(wrapped, min(255, max(0, wrapped)))
        self.assertIn(str(left + right), why["a"])

    def test_new_figure_reference_and_recall_ids_are_unambiguous(self):
        blocks = aspect_blocks()
        ids = [b["id"] for step in note("l15")["units"]["15b"]["steps"]
               for b in step["blocks"] if b["kind"] in ("guess", "recall", "levels")]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertNotIn("r4", ids)
        self.assertNotIn("15b-levels", ids)
        self.assertIn("15b-levels-v2", ids)
        figure = next(b for b in blocks if b["kind"] == "figure" and b["file"] == "assets/15b-6.png")
        self.assertTrue(Path(figure["path"]).is_file())
        self.assertTrue(any(b["kind"] == "why" and "4×4" in b["q"] for b in blocks))
