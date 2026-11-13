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

    def test_nonmember_receipt_does_not_store_a_token(self):
        self.assertEqual({"verified": True, "team": False}, self.identity.save({"verified": True, "team": False, "token": "unused"}))
        with self.assertRaises(CollectionError):
            self.identity.summary(7)

    def test_corrupt_receipt_is_preserved(self):
        self.identity.path.write_bytes(b"{broken")
        with self.assertRaises(CollectionError):
            self.identity.save({"verified": True, "team": False})
        self.assertEqual(b"{broken", self.identity.path.read_bytes())

    def test_device_flow_and_pending_token_stay_in_memory(self):
        device = {"verification_uri": "https://github.com/login/device", "device_code": "private-device-code",
                  "user_code": "TEST-CODE", "expires_in": 900, "interval": 5}
        def request(base, path, data=None, **kwargs):
            if path.endswith("/config"):
                return {"enabled": True, "client_id": "client123"}
            self.assertEqual("gho_" + "x" * 36, data["access_token"])
            return {"verified": True, "team": False}
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

    def test_installation_code_survives_new_client_and_reverification(self):
        first = self.identity.installation_nonce()
        second = Identity(study.ROOT, "another-user", home=self.tmp.name)
        self.assertEqual(first, second.installation_nonce())
