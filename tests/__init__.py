"""자동 수집을 켠 테스트의 파이썬 기록을 임시 경로로 분리함."""
import os
import tempfile


_python_records = tempfile.TemporaryDirectory(prefix="study_test_python_")
os.environ["STUDY_PYTHON_HOME"] = _python_records.name
