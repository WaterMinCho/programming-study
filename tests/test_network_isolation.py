"""시험용 HTTP는 루프백만 허용하고 외부 주소는 연결 전에 막음."""
import unittest
from unittest import mock
import urllib.request


class NetworkIsolationTest(unittest.TestCase):
    def test_external_http_is_rejected_before_transport(self):
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with mock.patch.object(urllib.request.HTTPSHandler, "https_open") as transport:
            with self.assertRaisesRegex(AssertionError, "외부 서버"):
                opener.open("https://example.invalid/")
            transport.assert_not_called()

    def test_loopback_http_can_reach_a_test_transport(self):
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with mock.patch.object(urllib.request.HTTPHandler, "http_open", side_effect=RuntimeError("local transport")) as transport:
            for host in ("localhost", "127.0.0.1", "[::1]"):
                with self.assertRaisesRegex(RuntimeError, "local transport"):
                    opener.open("http://" + host + "/")
            self.assertEqual(3, transport.call_count)
