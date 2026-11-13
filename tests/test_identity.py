# -*- coding: utf-8 -*-
"""기기 확인에 필요한 값만 보관하고 GitHub 토큰은 남기지 않는지 확인함."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import study
from learning_data.collection import CollectionError
from learning_data.identity import Identity


class IdentityTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.identity = Identity(study.ROOT, "tester", home=self.tmp.name)

    def test_local_receipt_keeps_only_device_access(self):
        result = self.identity.save({"verified": True, "team": True, "token": "a" * 64,
                                     "login": "private-name", "email": "private@example.test", "access_token": "gho_test"})
        self.assertEqual({"verified", "team", "token"}, set(result))
        text = self.identity.path.read_text()
        self.assertNotIn("private", text)
        self.assertNotIn("gho_test", text)
        self.assertEqual(result, self.identity.settings())

    def test_nonmember_device_key_cannot_read_statistics(self):
        self.assertEqual({"verified": True, "team": False, "token": "b" * 64}, self.identity.save({"verified": True, "team": False, "token": "b" * 64}))
        with self.assertRaises(CollectionError):
            self.identity.summary(7)

    def test_graded_response_validation_and_raw_only_server(self):
        self.identity.save({"verified": True, "team": True, "token": "a" * 64})
        rows = [{"at": "2026-11-13T12:00:00+09:00", "ai": 0, "python": 0} for _ in range(7)]
        raw = {"days": 7, "total": 100, "period_total": 0, "undated": 0, "series": rows,
               "installations": 1, "period_installations": 0, "accounts": 1, "period_accounts": 0}
        graded = {"total": 1, "period_total": 0, "undated": 1, "unknown": 2, "series": rows}
        with mock.patch("learning_data.identity.request", return_value=raw) as get:
            self.assertNotIn("graded", self.identity.summary(7))
            get.return_value = dict(raw, graded=graded)
            self.assertEqual(graded, self.identity.summary(7)["graded"])
            for invalid in (None, dict(graded, period_total=1), dict(graded, unknown=True), dict(graded, series=[])):
                get.return_value = dict(raw, graded=invalid)
                with self.assertRaises(CollectionError):
                    self.identity.summary(7)

    def test_activity_checks_missing_measurement_and_matching_buckets(self):
        from learning_data.identity import validate_activity
        at = "2026-11-13T12:00:00+09:00"
        row = dict(at=at, python=0, ai=0)
        activity = dict(distinct_cards=0, ai_input_schema=1, opens=[row],
                        inputs=[dict(row, ai=None, ai_unmeasured=False)], period_first_ai_measurement_at=None,
                        graded_metadata=dict(stem=0, concepts=0, revision=0, difficulty=0, ordered_timed=0, linked_input=0))
        validate_activity(activity, [row], {"period_total": 0})
        for change in (dict(inputs=[dict(row, ai=0, ai_unmeasured=False)]), dict(opens=[dict(row, at="other")]),
                       dict(graded_metadata=dict(activity["graded_metadata"], difficulty=1))):
            with self.assertRaises(ValueError):
                validate_activity(dict(activity, **change), [row], {"period_total": 0})

    def test_corrupt_receipt_is_preserved(self):
        self.identity.path.write_bytes(b"{broken")
        self.identity.save({"verified": True, "team": False, "token": "c" * 64})
        backups = list(self.identity.path.parent.glob("identity.json.broken-*"))
        self.assertEqual(1, len(backups))
        self.assertEqual(b"{broken", backups[0].read_bytes())
        self.assertTrue(self.identity.settings()["verified"])

    def test_device_flow_and_pending_token_stay_in_memory(self):
        device = {"verification_uri": "https://github.com/login/device", "device_code": "private-device-code",
                  "user_code": "TEST-CODE", "expires_in": 900, "interval": 5}
        def request(base, path, data=None, **kwargs):
            if path.endswith("/config"):
                return {"enabled": True, "client_id": "client123"}
            self.assertEqual("gho_" + "x" * 36, data["access_token"])
            return {"verified": True, "team": False, "token": "c" * 64}
        with mock.patch("learning_data.identity.request", side_effect=request), mock.patch("learning_data.identity.github", side_effect=[device, {"error": "authorization_pending"}, {"access_token": "gho_" + "x" * 36, "refresh_token": "private-refresh"}]):
            self.identity.begin()
            self.assertTrue(self.identity.poll()["pending"])
            self.identity.poll()
        self.assertIsNone(self.identity.pending_token)
        text = self.identity.path.read_text()
        self.assertNotIn("private", text)
        self.assertNotIn("gho_", text)

    def test_wrong_verification_address_is_rejected(self):
        with mock.patch("learning_data.identity.request", return_value={"enabled": True, "client_id": "client123"}), mock.patch("learning_data.identity.github", return_value={"verification_uri": "https://example.test", "device_code": "x", "user_code": "CODE", "expires_in": 900}):
            with self.assertRaises(CollectionError):
                self.identity.begin()

    def test_cancel_during_github_request_discards_pending_and_token_responses(self):
        for response in ({"error": "authorization_pending"}, {"error": "slow_down"}, {"access_token": "gho_synthetic-token"}):
            self.identity.nonce = "synthetic-nonce"
            self.identity.device = {"device_code": "synthetic-device", "interval": 5}
            self.identity.pending_token = None
            self.identity.client_id = "synthetic-client"
            def reply(*args, **kwargs):
                self.identity.cancel()
                return dict(response)
            with mock.patch("learning_data.identity.github", side_effect=reply), mock.patch("learning_data.identity.request") as request:
                with self.assertRaisesRegex(CollectionError, "중단"):
                    self.identity.poll()
                request.assert_not_called()
            self.assertIsNone(self.identity.pending_token)
            self.assertIsNone(self.identity.device)

    def test_installation_code_survives_new_client_and_reverification(self):
        first = self.identity.installation_nonce()
        second = Identity(study.ROOT, "another-user", home=self.tmp.name)
        self.assertEqual(first, second.installation_nonce())
