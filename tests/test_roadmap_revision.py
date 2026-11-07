"""운영체제의 줄 끝 차이로 같은 진로 목표를 다른 집단에 넣지 않음."""
import json
from pathlib import Path
import tempfile
import unittest

from aiprep.goals import catalog


class RoadmapRevisionTest(unittest.TestCase):
    def test_line_endings_and_json_layout_keep_revision_but_content_does_not(self):
        source = Path(__file__).resolve().parent.parent / "tools/roadmap/roadmap.json"
        data = json.loads(source.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "tools/roadmap/roadmap.json"
            path.parent.mkdir(parents=True)
            text = json.dumps(data, ensure_ascii=False, indent=2)
            path.write_bytes(text.encode("utf-8"))
            initial = catalog(temp)
            path.write_bytes(text.replace("\n", "\r\n").encode("utf-8"))
            self.assertEqual(initial, catalog(temp))
            path.write_bytes(json.dumps(data, sort_keys=True).encode("utf-8"))
            self.assertEqual(initial, catalog(temp))
            data["paths"][0]["title"] += " 개정"
            path.write_bytes(json.dumps(data).encode("utf-8"))
            self.assertNotEqual(initial["roadmap_revision"], catalog(temp)["roadmap_revision"])
