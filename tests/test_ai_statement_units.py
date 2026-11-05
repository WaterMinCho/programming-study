# -*- coding: utf-8 -*-
"""같은 보기 묶음 안에서도 문장을 실제 배운 단원의 읽기 기록과 노트로 연결함."""
import json
import shutil
from pathlib import Path

from tests.test_ai_service import Base, FIXTURE


class StatementUnitTest(Base):
    def test_statement_unit_controls_read_day_and_note_target(self):
        self.root = str(Path(self.tmp, "bank"))
        shutil.copytree(FIXTURE, self.root)
        path = Path(self.root, "items/i90/work/statements.json")
        data = json.loads(path.read_text(encoding="utf-8"))
        statement = next(s for t in data["topics"] for s in t["statements"] if s["id"] == "i90-s03")
        statement.update(unit="90a", step="90a/2")
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        sess = self.session()
        sess.mark_read("i90", "90b")
        self.assertIsNone(sess._state().read_day("i90-s03"))
        sess.mark_read("i90", "90a")
        self.assertEqual(sess.today(), sess._state().read_day("i90-s03"))
        target = sess.note_target("i90-s03")
        self.assertEqual(("i90", "90a/2"), (target["lesson"], target["step"]))
        self.assertEqual("90b", sess.card_info("i90-s04")["unit"])
