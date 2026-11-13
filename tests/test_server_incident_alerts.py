import unittest
from unittest.mock import patch

from tools.server_incident_alerts import relay


class Ledger:
    def __init__(self):
        self.rows = []

    def pages(self, path):
        return reversed(self.rows)

    def post(self, path, data):
        self.rows.append(dict(data))


class IncidentAlertsTest(unittest.TestCase):
    def test_repeat_and_recovery(self):
        github = Ledger()
        opened = ("2026-01-01", "42", "started_at", "test")
        resolved = ("2026-01-02", "42", "resolved_at", "test")
        with patch("tools.server_incident_alerts.send") as send:
            for notices in ([opened], [opened], [opened, resolved], [opened, resolved]):
                relay(github, "a" * 40, notices, "webhook")
        self.assertEqual([args.args[0]["text"] for args in send.call_args_list],
                         ["🔴 장애 감지 · ROKEY 연결 테스트", "🟢 복구 · ROKEY 연결 테스트"])

    def test_ambiguous_response_is_not_resent(self):
        github = Ledger()
        notices = [("2026-01-01", "42", "started_at", "health")]
        with patch("tools.server_incident_alerts.send", side_effect=TimeoutError) as send:
            with self.assertRaises(TimeoutError):
                relay(github, "a" * 40, notices, "webhook")
            with self.assertRaises(RuntimeError):
                relay(github, "a" * 40, notices, "webhook")
            self.assertEqual(send.call_count, 1)
