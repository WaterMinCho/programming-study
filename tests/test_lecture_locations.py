# -*- coding: utf-8 -*-
"""강의 위치와 우리 노트 위치를 구별하고 화면에 보이는 글만 검사함."""
import json
import unicodedata
import unittest

from tools import lecture_locations, web_lint


class LocationTest(unittest.TestCase):
    def test_external_locator_spellings_and_spacing(self):
        for text in ("4차시 슬라이드 8쪽", "4차시슬p8", "(노트북 01 셀 18)", "노트북01[18]",
                     "노트북 셀2", "강사 요약본 1주차 16쪽", "요약 1주차 p5", "대학원02 p22",
                     "LectureNote 01 p3", "4차시 과제 2번", "강의 자료 3쪽", "슬라이드3쪽",
                     "1주차 과제 5차시 p2", "4차시 **슬라이드** `8쪽`",
                     "노트북 01의 77번 셀", "노트북 02의 43번 셀", "대학원 강의안 02의 22쪽"):
            with self.subTest(text=text):
                self.assertTrue(lecture_locations.find(text), text)
                self.assertTrue(lecture_locations.find(unicodedata.normalize("NFD", text)), text)

    def test_internal_notes_and_official_document_names_remain_available(self):
        for text in ("5차시 여섯째 단원 3단계", "5f/3 단계", "PyTorch 문서 BatchNorm1d",
                     "Autograd mechanics 공식 문서", "Jupyter 노트북에서 셀을 실행합니다.",
                     "슬라이드의 제목을 입력합니다."):
            self.assertEqual([], lecture_locations.find(text), text)

    def test_correction_and_supplement_sentences_allow_locations_but_parentheses_do_not(self):
        for kind in ("정정", "보충 설명"):
            good = "> **[%s]** 4차시 슬라이드 57쪽은 이 값을 적었습니다.\n> 노트북 셀 2도 같은 값을 적었습니다." % kind
            self.assertEqual([], lecture_locations.find(good, markdown=True))
            for text in ("> **[%s]** 값을 확인합니다(4차시 슬라이드 57쪽)." % kind,
                         "> **[%s]** 값을 확인합니다(원래 값(오류) 4차시 슬라이드 57쪽)." % kind,
                         good + "\n\n4차시 슬라이드 57쪽을 봅니다.",
                         good + "\n> **[참고]** 노트북 셀 2를 봅니다."):
                self.assertTrue(lecture_locations.find(text, markdown=True), text)
            self.assertTrue(lecture_locations.find(good))
        self.assertTrue(lecture_locations.find("정정: 4차시 슬라이드 57쪽을 봅니다.", markdown=True))

    def test_markdown_blocks_captions_frames_and_code_comments_are_checked(self):
        texts = ["본문(4차시 슬라이드 3쪽).", "| 항목 | 슬라이드 3쪽 |",
                 "```figure\n캡션: 슬라이드 3쪽\n프레임:\n1. 노트북 셀 2 (1000ms)\n```",
                 "```python\n# 4차시 슬라이드 3쪽\n```",
                 "```ai-recall\n" + json.dumps({"q": "노트북 셀 2", "why": "슬라이드 3쪽"}) + "\n```",
                 "~~~ai-levels\n" + json.dumps({"levels": [{"text": "슬라이드 3쪽"}]}) + "\n~~~"]
        for text in texts:
            self.assertTrue(lecture_locations.find(text, markdown=True), text)
        self.assertEqual([], lecture_locations.find("<!-- 4차시 슬라이드 3쪽 -->", markdown=True))

    def test_json_metadata_is_not_learner_text(self):
        block = {"q": "5차시 여섯째 단원 3단계를 읽습니다.", "ref": ["4차시 슬 p3"],
                 "facts": [{"where": ["노트북 셀 2"]}], "sources": ["대학원 02 p22"]}
        markdown = "```ai-recall\n%s\n```" % json.dumps(block)
        self.assertEqual([], lecture_locations.find(markdown, markdown=True))
        block["why"] = "슬라이드 3쪽을 봅니다."
        self.assertTrue(lecture_locations.find("```ai-recall\n%s\n```" % json.dumps(block), markdown=True))

    def test_web_lint_enforces_locations_without_the_external_checker(self):
        report = web_lint.Report("fixture")
        web_lint.style_check(report, [], [("page.md", "본문(4차시 슬라이드 3쪽).")],
                             [("caption", "노트북 셀 2", True)])
        self.assertEqual(2, len(report.errors))
        self.assertTrue(all(row[2] == lecture_locations.RULE for row in report.errors))

    def test_duplicate_location_reports_keep_other_style_failures(self):
        def external(text, commit, name):
            return [(lecture_locations.RULE, "슬라이드 3쪽"), ("다른 문장 규칙", "확인할 문장")]
        report = web_lint.Report("fixture")
        web_lint.style_check(report, [("external", external)], [("page.md", "슬라이드 3쪽")], [])
        self.assertEqual([lecture_locations.RULE, "말투 다른 문장 규칙"], [row[2] for row in report.errors])


if __name__ == "__main__":
    unittest.main()
