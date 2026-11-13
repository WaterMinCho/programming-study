"""시험 기록은 임시 경로로 분리하고 HTTP는 루프백에 한정함."""
import os
import tempfile
import urllib.parse
import urllib.request


_python_records = tempfile.TemporaryDirectory(prefix="study_test_python_")
os.environ["STUDY_PYTHON_HOME"] = _python_records.name


def _local_http_only(original):
    def open_local(opener, address, *args, **kwargs):
        url = address.full_url if isinstance(address, urllib.request.Request) else address
        host = urllib.parse.urlsplit(url).hostname
        if host is not None and host not in ("localhost", "127.0.0.1", "::1"):
            raise AssertionError("시험에서 외부 서버를 호출할 수 없습니다.")
        return original(opener, address, *args, **kwargs)
    open_local.study_test_guard = True
    return open_local


if not getattr(urllib.request.OpenerDirector.open, "study_test_guard", False):
    urllib.request.OpenerDirector.open = _local_http_only(urllib.request.OpenerDirector.open)
