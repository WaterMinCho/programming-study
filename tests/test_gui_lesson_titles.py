"""차시 번호가 포함된 자료 이름을 목록과 제목에 한 번만 표시하는지 확인함."""
import copy
from unittest import mock

from tests import guikit
from tests.test_gui_ai import AiTest
from gui import ai_text


class LessonTitleTest(AiTest):
    def test_existing_lesson_numbers_are_not_added_a_second_time(self):
        cases = ((13, "13차시 사전학습한 특징", "13차시 사전학습한 특징"),
                 (1, "출력과 정답", "1차시 출력과 정답"),
                 (17, "17차시", "17차시"))
        for no, title, expected in cases:
            with self.subTest(no=no):
                self.assertEqual(ai_text.lesson_title(no, title), expected)

    def test_home_and_lesson_header_keep_the_same_single_number(self):
        win = self.boot()
        overview = copy.deepcopy(win.ai.overview())
        row = next(r for r in overview["lessons"] if r["id"] == "i90")
        row["title"] = "90차시 시험 차시"
        lesson = dict(win.ai.lesson("i90"), title=row["title"])
        with mock.patch.object(win.ai, "overview", return_value=overview), \
                mock.patch.object(win.ai, "lesson", return_value=lesson):
            win.go_ai()
            guikit.pump()
            self.assertEqual(win.ai_home.lesson_list.rows[0].title.text(), "90차시 시험 차시")
            win.open_ai_lesson("i90")
            guikit.pump()
            self.assertEqual(win.ai_lesson.title.text(), "90차시 시험 차시")
