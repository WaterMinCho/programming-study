# -*- coding: utf-8 -*-
"""채점 러너 테스트. 가짜 문제를 채점해 학생 코드가 메모리를 끝없이 쓸 때 채점이 멈추는지 확인함.

실행: python -m unittest tests.test_runner
"""
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import study  # noqa: E402

try:
    import resource
except ImportError:  # Windows 에는 없음
    resource = None

MB = 1024 * 1024
LIMIT_MB = 128  # 테스트가 빨리 끝나게 상한을 낮춤
ENDLESS_GENERATOR = "def numbers():\n    n = 0\n    while True:\n        yield n\n        n += 1\n"
ENDLESS_C_LOOP = "import itertools\n\n\ndef numbers():\n    return itertools.count()\n"
SLOW_BUT_RIGHT = "import time\n\n\ndef numbers():\n    time.sleep(0.5)\n    return iter([0, 1, 2])\n"


def peak_child_memory():
    """끝난 자식 프로세스 가운데 메모리를 가장 많이 쓴 것의 사용량(바이트)."""
    peak = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    return peak if sys.platform == "darwin" else peak * 1024  # 맥은 바이트, 리눅스는 KB


class MemoryLimitTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="study_test_")
        patch = mock.patch.object(study, "MEMORY_LIMIT_MB", LIMIT_MB)
        patch.start()
        self.addCleanup(patch.stop)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def grade(self, source):
        """numbers() 를 list() 로 받는 가짜 문제를 채점함. 상한이 안 걸려도 3초 뒤에는 끝남."""
        path = os.path.join(self.tmp, "p01.py")
        study.write_text(path, source)
        spec = {"mode": "exec", "timeout": 3, "cases": [{"code": "print(list(numbers()))", "stdout": "[0, 1, 2]\n"}]}
        return study.run_problem(spec, path)

    def test_endless_generator_is_stopped_at_the_memory_limit(self):
        ok, passed, detail = self.grade(ENDLESS_GENERATOR)
        self.assertEqual((ok, passed), (False, 0))
        self.assertIn("메모리 초과", detail)
        self.assertIn("%dMB" % LIMIT_MB, detail)
        if resource:  # 감시 간격만큼은 상한을 넘을 수 있어 여유를 둠
            self.assertLess(peak_child_memory(), 4 * LIMIT_MB * MB)

    def test_loop_that_never_returns_to_python_is_stopped_too(self):
        # list(itertools.count()) 는 C 안에서만 돌아서 자식 프로세스의 다른 스레드가 끼어들 틈이 없음
        ok, passed, detail = self.grade(ENDLESS_C_LOOP)
        self.assertEqual((ok, passed), (False, 0))
        self.assertIn("메모리 초과", detail)

    def test_slow_solution_under_the_limit_still_passes(self):
        self.assertEqual(self.grade(SLOW_BUT_RIGHT), (True, 1, ""))


if __name__ == "__main__":
    unittest.main()
