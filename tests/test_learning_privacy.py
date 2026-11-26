# -*- coding: utf-8 -*-
"""동의·거부·재전송·철회와 공개 제출의 분리를 확인함."""
import hashlib
import io
import json
import os
from pathlib import Path
import secrets
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock
import uuid

from aiprep.collection import Collection, CollectionError, NOTICE, stamp
from aiprep.privacy import Consent, receipt
from aiprep import sharing
from learning_server import app
from learning_server.app import Database, application
from learning_server.storage import usage
from learning_data.collection import packed
from learning_data.sharing import request as http_request
from submission_api import Client


class PrivacyTest(unittest.TestCase):
    def test_operator_name_update_keeps_existing_v3_receipt_valid(self):
        from learning_data import privacy

        old = dict(privacy.receipt(), policy="2026-11-13-v3",
                   policy_hash="534b9e08a6f7eb0b3cb9a975a55db06c3030aa8723083e740878707caf1cd73b")
        self.assertEqual(old, privacy.validate_receipt(old))
        self.assertEqual(dict(privacy.NOTICE_ROWS)["운영자·문의"], "WaterMinCho · " + privacy.CONTACT)

    def test_account_requests_reject_future_consent_without_changing_records(self):
        import datetime
        identity = self.verified("account-1")
        self.consent.choose(True)
        self.assertFalse(self.consent.synchronize(identity=identity)["errors"])
        with self.db.connect() as db:
            before = {table: db.execute("SELECT * FROM " + table).fetchall()
                      for table in ("research_accounts", "research_links", "events")}
        future = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=5)).isoformat()
        for method in ("POST", "DELETE"):
            with self.subTest(method=method):
                code, error = self.call("/v1/identity/research-link", {"consented_at": future},
                                        identity.settings()["token"], method)
                self.assertEqual(400, code)
                self.assertIn("미래", error["error"])
                with self.db.connect() as db:
                    self.assertEqual(before, {table: db.execute("SELECT * FROM " + table).fetchall() for table in before})

    def test_saved_proof_prevents_replacement_after_fast_clock_and_delayed_reconnect(self):
        import datetime
        from learning_data.privacy import save
        from learning_server.team import Access
        for delayed in (False, True):
            with self.subTest(delayed=delayed):
                self.setUp()
                first, second = self.verified("account-1"), self.verified("account-1")
                other = self.computer("other")
                for consent, identity in ((self.consent, first), (other, second)):
                    consent.choose(True)
                    self.assertFalse(consent.synchronize(identity=identity)["errors"])
                saved = other.path.with_name("research-link.json").read_bytes()
                state = other.settings()
                ahead = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=5)
                state["receipt"]["at"] = ahead.isoformat()
                save(other.path, state)
                self.consent.withdraw()
                self.assertTrue(self.consent.synchronize(identity=first)["withdrawn"])
                self.consent.choose(True)
                self.collections["ai"].emit("answer", {"result": "pass", "card": "new-consent"})
                self.assertFalse(self.consent.synchronize(identity=first)["errors"])
                with self.db.connect() as db:
                    before = {table: db.execute("SELECT * FROM " + table).fetchall()
                              for table in ("research_accounts", "research_links", "events")}
                original = Access.research_link
                server_now = ahead + datetime.timedelta(seconds=1) if delayed else datetime.datetime.now(datetime.timezone.utc)
                def server_clock(access, *args, **kwargs):
                    return original(access, *args, **kwargs, now=server_now)
                with mock.patch.object(Access, "research_link", server_clock), mock.patch.object(sharing, "request", wraps=self.transport) as wire:
                    self.assertTrue(other.synchronize(identity=second)["errors"])
                    self.assertEqual(["/v1/research-link/status"], [call.args[1] for call in wire.call_args_list])
                    self.assertEqual(saved, other.path.with_name("research-link.json").read_bytes())
                    self.assertTrue(other.synchronize(identity=second)["withdrawn"])
                with self.db.connect() as db:
                    self.assertEqual(before, {table: db.execute("SELECT * FROM " + table).fetchall() for table in before})
                self.assertFalse(self.consent.synchronize(identity=first)["errors"])

    def test_unsent_old_consent_uses_server_marker_after_clock_catches_up(self):
        import datetime
        from learning_data.privacy import save
        from learning_server.team import Access
        identity = self.verified("account-1")
        self.consent.choose(True)
        ahead = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=5)
        state = self.consent.settings()
        state["receipt"]["at"] = ahead.isoformat()
        save(self.consent.path, state)
        owner, owner_identity = self.computer("owner"), self.verified("account-1")
        owner.choose(True)
        self.assertFalse(owner.synchronize(identity=owner_identity)["errors"])
        owner.withdraw()
        self.assertTrue(owner.synchronize(identity=owner_identity)["withdrawn"])
        marker = owner.settings()["withdrawal_seen"]
        owner.choose(True)
        owner.collections["ai"].emit("answer", {"result": "pass"})
        self.assertFalse(owner.synchronize(identity=owner_identity)["errors"])
        with self.db.connect() as db:
            before = {table: db.execute("SELECT * FROM " + table).fetchall()
                      for table in ("research_accounts", "research_links", "events")}
        original = Access.research_link
        def server_clock(access, *args, **kwargs):
            return original(access, *args, **kwargs, now=ahead + datetime.timedelta(seconds=1))
        with mock.patch.object(Access, "research_link", server_clock):
            old_delete = {"consented_at": ahead.isoformat(), "after_withdrawal": None}
            self.assertEqual((200, {"deleted": True, "withdrawn_at": marker}),
                             self.call("/v1/identity/research-link", old_delete, identity.settings()["token"], "DELETE"))
            self.assertTrue(self.consent.synchronize(identity=identity)["errors"])
            self.assertEqual(marker, self.consent.settings()["withdrawal_seen"])
            self.assertIsNone(self.consent.settings()["after_withdrawal"])
            self.assertTrue(self.consent.synchronize(identity=identity)["withdrawn"])
            with self.db.connect() as db:
                self.assertEqual(before, {table: db.execute("SELECT * FROM " + table).fetchall() for table in before})
            self.consent.choose(True)
            self.assertEqual(marker, self.consent.settings()["after_withdrawal"])
            self.assertFalse(self.consent.synchronize(identity=identity)["errors"])
            self.assertEqual(owner._saved_research(), self.consent._saved_research())

    def test_missing_proof_file_preserves_linked_settings_and_requires_recovery(self):
        first, second = self.verified("account-1"), self.verified("account-1")
        other = self.computer("other")
        for consent, identity in ((self.consent, first), (other, second)):
            consent.choose(True)
            self.assertFalse(consent.synchronize(identity=identity)["errors"])
        path = other.path.with_name("research-link.json")
        path.unlink()
        settings = {Path(sharing.Sharing(store).path): Path(sharing.Sharing(store).path).read_bytes()
                    for store in other.collections.values()}
        self.consent.withdraw()
        self.assertTrue(self.consent.synchronize(identity=first)["withdrawn"])
        self.consent.choose(True)
        self.collections["ai"].emit("answer", {"result": "pass"})
        self.assertFalse(self.consent.synchronize(identity=first)["errors"])
        with self.db.connect() as db:
            before = {table: db.execute("SELECT * FROM " + table).fetchall()
                      for table in ("research_accounts", "research_links", "events")}
        with mock.patch.object(sharing, "request", wraps=self.transport) as wire:
            result = other.synchronize(identity=second)
            wire.assert_not_called()
        self.assertTrue(any("복구" in error for error in result["errors"]))
        self.assertFalse(path.exists())
        self.assertEqual(settings, {file: file.read_bytes() for file in settings})
        with self.db.connect() as db:
            self.assertEqual(before, {table: db.execute("SELECT * FROM " + table).fetchall() for table in before})

    def test_automatic_scope_same_instant_cannot_reenable_using_another_timezone(self):
        self.consent.choose(True)
        self.consent.set_auto_submission(False)
        current = self.consent.settings()["receipt"]
        current["automatic_submission"]["at"] = "2026-11-23T12:00:00+09:00"
        packet = {"participant": str(uuid.uuid4()), "notice": NOTICE,
                  "registration_secret": secrets.token_hex(32), "consent": current}
        code, enrolled = self.call("/v1/enroll/open", packet)
        self.assertEqual(200, code)
        late = dict(current, automatic_submission=dict(current["automatic_submission"],
                                                       accepted=True, at="2026-11-23T03:00:00+00:00"))
        self.assertEqual(409, self.call("/v1/consent", {"consent": late}, enrolled["token"])[0])
        with self.db.connect() as db:
            saved = json.loads(db.execute("SELECT receipt FROM open_enrollments WHERE participant=?",
                                          (packet["participant"],)).fetchone()[0])
        self.assertEqual(current, saved)

    def test_late_revoked_reply_does_not_withdraw_a_new_choice(self):
        for route in ("/v1/identity/research-link", "/v1/consent"):
            with self.subTest(route=route):
                self.setUp()
                identity = self.verified("account-1")
                self.consent.choose(True)
                old = self.consent.settings()["choice"]
                marker = "2026-11-23T00:00:00+00:00"
                def delayed(base, path, *args, **kwargs):
                    if path == route:
                        self.consent.choose(True)
                        self.collections["ai"].emit("answer", {"result": "pass", "card": "new-local"})
                        raise CollectionError("늦은 응답", status=401, code="revoked", withdrawn_at=marker)
                    return self.transport(base, path, *args, **kwargs)
                with mock.patch.object(sharing, "request", delayed):
                    self.assertFalse(self.consent.synchronize(identity=identity)["errors"])
                state = self.consent.settings()
                self.assertNotEqual(old, state["choice"])
                self.assertTrue(state["accepted"])
                self.assertFalse(state.get("withdraw_pending"))
                self.assertEqual(marker, state["withdrawal_seen"])
                self.assertIsNone(state["after_withdrawal"])
                self.assertTrue(all(Path(store.path).exists() and store.status()["enabled"] for store in self.collections.values()))

    def test_withdrawal_marker_increases_when_server_time_repeats_or_goes_back(self):
        import datetime
        from learning_server.team import Access
        access = Access(self.db)
        identity = self.verified("account-1")
        auth = "Bearer " + identity.settings()["token"]
        data = {"consented_at": "2026-11-01T00:00:00+00:00"}
        now = datetime.datetime(2026, 11, 23, tzinfo=datetime.timezone.utc)
        marker = None
        for clock in (now, now, now-datetime.timedelta(minutes=5)):
            data["after_withdrawal"] = marker
            access.research_link(auth, data, now=clock)
            result = access.research_link(auth, data, delete=True, now=clock)
            if marker:
                self.assertGreater(datetime.datetime.fromisoformat(result["withdrawn_at"]), datetime.datetime.fromisoformat(marker))
            marker = result["withdrawn_at"]
            self.assertEqual(result, access.research_link(auth, data, delete=True, now=clock))
        data["after_withdrawal"] = marker
        linked = access.research_link(auth, data, now=now)
        with self.db.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            latest = self.db.remove_linked(db, linked["link"], (now-datetime.timedelta(days=1)).isoformat())
        self.assertGreater(datetime.datetime.fromisoformat(latest), datetime.datetime.fromisoformat(marker))

    def test_old_saved_proof_keeps_its_marker_when_a_new_choice_already_knows_the_withdrawal(self):
        first, second = self.verified("account-1"), self.verified("account-1")
        other = self.computer("other")
        for consent, identity in ((self.consent, first), (other, second)):
            consent.choose(True)
            self.assertFalse(consent.synchronize(identity=identity)["errors"])
        self.consent.withdraw()
        self.assertTrue(self.consent.synchronize(identity=first)["withdrawn"])
        marker = self.consent.settings()["withdrawal_seen"]
        self.consent.choose(True)
        self.collections["ai"].emit("answer", {"result": "pass"})
        self.assertFalse(self.consent.synchronize(identity=first)["errors"])
        other._remember_withdrawal(marker)
        other.choose(True)
        self.assertEqual(marker, other.settings()["after_withdrawal"])
        self.assertIsNone(other._saved_research()["after_withdrawal"])
        with self.db.connect() as db:
            before = {table: db.execute("SELECT * FROM " + table).fetchall()
                      for table in ("research_accounts", "research_links", "events")}
        self.assertTrue(other.synchronize(identity=second)["errors"])
        self.assertTrue(other.synchronize(identity=second)["withdrawn"])
        with self.db.connect() as db:
            self.assertEqual(before, {table: db.execute("SELECT * FROM " + table).fetchall() for table in before})

    def test_http_errors_preserve_absent_null_and_current_withdrawal_markers(self):
        import urllib.error
        for marker in (..., None, "2026-11-23T00:00:00+00:00"):
            failure = {"error": "철회한 동의", "code": "revoked"}
            if marker is not ...:
                failure["withdrawn_at"] = marker
            error = urllib.error.HTTPError("https://example.test", 401, "revoked", {}, io.BytesIO(packed(failure).encode()))
            opener = mock.Mock()
            opener.open.side_effect = error
            with mock.patch("urllib.request.build_opener", return_value=opener), self.assertRaises(CollectionError) as raised:
                http_request("https://example.test", "/v1/identity/research-link", {})
            self.assertEqual(marker, raised.exception.withdrawn_at)
            self.assertEqual("revoked", raised.exception.code)

    def test_late_consent_cannot_replace_newer_policy_or_consent_time(self):
        import datetime
        from learning_data import privacy
        self.consent.choose(True)
        self.consent.set_auto_submission(False)
        current = self.consent.settings()["receipt"]
        current["at"] = "2026-11-23T12:00:00+09:00"
        packet = {"participant": str(uuid.uuid4()), "notice": NOTICE,
                  "registration_secret": secrets.token_hex(32), "consent": current}
        for version, at in (("2026-11-13-v3", "2026-11-22T12:00:00+09:00"),
                            ("2026-11-13-v3", current["at"]),
                            ("2026-11-13-v3", "2026-11-23T03:00:00+00:00"),
                            ("2026-11-13-v3", "2026-11-24T12:00:00+09:00"),
                            (privacy.POLICY_VERSION, "2026-11-22T12:00:00+09:00")):
            with self.subTest(version=version, at=at):
                packet["participant"] = str(uuid.uuid4())
                code, enrolled = self.call("/v1/enroll/open", packet)
                self.assertEqual(200, code)
                late = dict(current, policy=version, policy_hash=privacy.SUPPORTED_POLICIES[version], at=at,
                            automatic_submission=dict(current["automatic_submission"], accepted=True))
                self.assertEqual(409, self.call("/v1/consent", {"consent": late}, enrolled["token"])[0])
                with self.db.connect() as db:
                    saved = json.loads(db.execute("SELECT receipt FROM open_enrollments WHERE participant=?",
                                                  (packet["participant"],)).fetchone()[0])
                self.assertEqual(current, saved)
        retry = {key: value for key, value in current.items() if key != "automatic_submission"}
        retry["at"] = datetime.datetime.fromisoformat(current["at"]).astimezone(datetime.timezone.utc).isoformat()
        self.assertEqual(200, self.call("/v1/consent", {"consent": retry}, enrolled["token"])[0])
        with self.db.connect() as db:
            saved = json.loads(db.execute("SELECT receipt FROM open_enrollments WHERE participant=?",
                                          (packet["participant"],)).fetchone()[0])
        self.assertEqual(current["automatic_submission"], saved.get("automatic_submission"))

    def test_server_preserves_automatic_scope_only_for_the_same_consent(self):
        from learning_data import privacy
        self.consent.choose(True)
        self.consent.set_auto_submission(True)
        current = self.consent.settings()["receipt"]
        for change in ("policy", "at"):
            with self.subTest(change=change):
                old = dict(current)
                if change == "policy":
                    old.update(policy="2026-11-13-v3", policy_hash=privacy.SUPPORTED_POLICIES["2026-11-13-v3"])
                else:
                    old["at"] = "2026-11-01T00:00:00+00:00"
                packet = {"participant": str(uuid.uuid4()), "notice": NOTICE,
                          "registration_secret": secrets.token_hex(32), "consent": old}
                code, enrolled = self.call("/v1/enroll/open", packet)
                self.assertEqual(200, code)
                retry = {key: value for key, value in old.items() if key != "automatic_submission"}
                self.assertEqual(200, self.call("/v1/consent", {"consent": retry}, enrolled["token"])[0])
                with self.db.connect() as db:
                    kept = json.loads(db.execute("SELECT receipt FROM open_enrollments WHERE participant=?",
                                                 (packet["participant"],)).fetchone()[0])
                self.assertEqual(old, kept)
                fresh = {key: value for key, value in current.items() if key != "automatic_submission"}
                self.assertEqual(200, self.call("/v1/consent", {"consent": fresh}, enrolled["token"])[0])
                with self.db.connect() as db:
                    saved = json.loads(db.execute("SELECT receipt FROM open_enrollments WHERE participant=?",
                                                  (packet["participant"],)).fetchone()[0])
                self.assertEqual(fresh, saved)

    def test_purpose_update_asks_old_consenters_again_and_stops_collection_until_then(self):
        from learning_data import privacy
        for old_version in ("2026-11-13-v3", "2026-11-12-v2"):
            with self.subTest(old_version):
                self.setUp()
                old_hash = privacy.SUPPORTED_POLICIES[old_version]
                with mock.patch.multiple(privacy, POLICY_VERSION=old_version, POLICY_HASH=old_hash):
                    self.consent.choose(True)
                    self.consent.set_auto_submission(True)
                    for store in self.collections.values():
                        self.assertTrue(store.emit("answer", {"result": "pass", "card": "q0"}))
                old = self.consent.settings()["receipt"]
                self.assertEqual(old, privacy.validate_receipt(old, automatic=True))
                self.assertTrue(self.consent.needs_choice())
                self.assertFalse(self.consent.needs_auto_choice())
                for store in self.collections.values():
                    store.initialize_distribution()
                    self.assertFalse(store.status()["enabled"])
                    self.assertFalse(store.emit("answer", {"result": "pass", "card": "q1"}))
                self.assertEqual({"sent": 0, "errors": []}, self.consent.synchronize())
                with self.db.connect() as db:
                    self.assertEqual(0, db.execute("SELECT count(*) FROM participants").fetchone()[0])
                epochs = {name: store.status()["epoch"] for name, store in self.collections.items()}
                again = self.consent.choose(True)
                self.assertEqual(privacy.POLICY_VERSION, again["policy"])
                self.assertEqual(privacy.POLICY_VERSION, again["receipt"]["policy"])
                self.assertFalse(self.consent.needs_choice())
                self.assertTrue(self.consent.needs_auto_choice())
                for name, store in self.collections.items():
                    self.assertTrue(store.status()["enabled"])
                    self.assertNotEqual(epochs[name], store.status()["epoch"])
                    self.assertTrue(store.emit("answer", {"result": "pass", "card": "q2"}))
                result = self.consent.synchronize()
                self.assertFalse(result["errors"])
                with self.db.connect() as db:
                    cards = {json.loads(row[0])["data"].get("card") for row in db.execute("SELECT payload FROM events")}
                self.assertIn("q2", cards)
                self.assertFalse({"q0", "q1"} & cards)

    def test_v3_to_v4_reconsent_stores_the_received_receipt_without_old_automatic_scope(self):
        from learning_data import privacy
        old_policy = "2026-11-13-v3"
        with mock.patch.multiple(privacy, POLICY_VERSION=old_policy, POLICY_HASH=privacy.SUPPORTED_POLICIES[old_policy]):
            self.consent.choose(True)
            self.consent.set_auto_submission(True)
            old = self.consent.settings()["receipt"]
            for store in self.collections.values():
                packet = {"participant": store.status()["participant"], "notice": NOTICE,
                          "registration_secret": secrets.token_hex(32), "consent": old}
                code, enrolled = self.call("/v1/enroll/open", packet)
                self.assertEqual(200, code)
                sharing.Sharing(store)._save(dict(enrolled, url=self.consent.server, sequence=store.latest_sequence(),
                                                 consent_policy=old_policy, consent_receipt=old, include_answers=False))
        self.consent.choose(True)
        self.assertTrue(self.consent.needs_auto_choice())
        current = self.consent.settings()["receipt"]
        self.assertNotIn("automatic_submission", current)
        self.assertFalse(self.consent.synchronize()["errors"])
        with self.db.connect() as db:
            saved = [json.loads(row[0]) for row in db.execute("SELECT receipt FROM open_enrollments")]
        self.assertEqual([current, current], saved)

    def test_old_decline_or_withdrawal_is_not_asked_again(self):
        from learning_data import privacy
        old_version = "2026-11-13-v3"
        with mock.patch.multiple(privacy, POLICY_VERSION=old_version, POLICY_HASH=privacy.SUPPORTED_POLICIES[old_version]):
            self.consent.choose(False)
        self.assertFalse(self.consent.needs_choice())
        self.assertFalse(self.consent.settings()["accepted"])
        with mock.patch.multiple(privacy, POLICY_VERSION=old_version, POLICY_HASH=privacy.SUPPORTED_POLICIES[old_version]):
            self.consent.choose(True)
            self.consent.withdraw()
            self.assertTrue(self.consent.synchronize()["withdrawn"])
        self.assertFalse(self.consent.needs_choice())
        self.assertEqual(old_version, self.consent.settings()["policy"])
        for store in self.collections.values():
            self.assertFalse(store.emit("answer", {"result": "pass"}))

    def test_unknown_or_tampered_policy_is_asked_again(self):
        from learning_data import privacy
        self.consent.choose(True)
        state = self.consent.settings()
        for broken in (dict(state, policy_hash=privacy.SUPPORTED_POLICIES["2026-11-13-v3"]), dict(state, policy="2026-11-01-v1")):
            privacy.save(self.consent.path, broken)
            self.assertTrue(self.consent.needs_choice())
            with self.assertRaises(ValueError):
                privacy.validate_receipt(dict(state["receipt"], policy=broken["policy"], policy_hash=broken["policy_hash"]))

    def test_unmocked_http_is_rejected_by_the_fixture(self):
        import urllib.request
        with self.assertRaisesRegex(AssertionError, "외부 서버"):
            urllib.request.build_opener().open("https://example.invalid")

    def test_invalid_saved_consent_time_stays_a_recoverable_sync_error(self):
        self.consent.choose(True)
        from learning_data.privacy import save
        state = self.consent.settings()
        state["receipt"]["at"] = "2026-11-13T13:00:00"
        save(self.consent.path, state)
        result = self.consent.synchronize()
        self.assertEqual(0, result["sent"])
        self.assertTrue(result["errors"])
        self.assertTrue(all("시간대" in text for text in result["errors"]))

    def test_incomplete_open_connection_is_a_recoverable_error_for_manual_sync(self):
        self.consent.choose(True)
        store = self.collections["ai"]
        share = sharing.Sharing(store)
        with mock.patch.object(sharing, "request", side_effect=CollectionError("offline")):
            with self.assertRaises(CollectionError):
                share.connect_open("https://example.test", self.consent.settings()["receipt"])
        self.assertNotIn("token", share.settings())
        with self.assertRaisesRegex(CollectionError, "서버 연결을 마친 뒤"):
            share.sync("https://example.test")
        self.assertTrue(share.settings()["enroll_sent"])

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.repo = self.root / "repo"
        self.collections = {name: Collection(str(self.root / name), str(self.repo), track=name) for name in ("python", "ai")}
        self.consent = Consent(self.collections, "https://example.test")
        self.db = Database(self.root / "server/learning.sqlite3")
        self.app = application(self.db, legacy_contract=True)
        for patcher in (mock.patch.dict(os.environ, {"STUDY_OPEN_REGISTRATION": "1"}),
                        mock.patch.object(sharing, "request", self.transport),
                        mock.patch("learning_data.submission.request", self.transport),
                        mock.patch("urllib.request.OpenerDirector.open", side_effect=AssertionError("시험에서 외부 서버를 호출할 수 없습니다."))):
            patcher.start()
            self.addCleanup(patcher.stop)

    def call(self, path, data=None, token=None, method="POST"):
        raw = packed(data).encode("utf-8")
        env = {"REQUEST_METHOD": method, "PATH_INFO": path, "CONTENT_TYPE": "application/json",
               "CONTENT_LENGTH": str(len(raw)), "wsgi.input": io.BytesIO(raw)}
        if token:
            env["HTTP_AUTHORIZATION"] = "Bearer " + token
        status = []
        value = json.loads(b"".join(self.app(env, lambda code, headers: status.append(code))))
        return int(status[0].split()[0]), value

    def transport(self, base, path, data=None, token=None, method="POST", **kwargs):
        status, value = self.call(path, data, token, method)
        if status != 200:
            raise CollectionError(value["error"], status=status, code=value.get("code"),
                                  withdrawn_at=value.get("withdrawn_at", ...))
        return value

    def computer(self, name):
        """같은 서버로 보내는 다른 컴퓨터의 수집 폴더와 동의 설정을 만듦."""
        collections = {track: Collection(str(self.root / name / track), str(self.repo), track=track) for track in ("python", "ai")}
        return Consent(collections, "https://example.test")

    def verified(self, account):
        """account 계정으로 본인 확인을 마친 기기 키를 서버에 넣고 그 키를 저장한 기기 인증을 돌려줌."""
        from learning_server.app import hashed
        from learning_server.team import Access
        token = secrets.token_hex(32)
        with self.db.connect() as db:
            db.execute("INSERT INTO identity_grants (token_hash,policy,created,member,account_hash) VALUES (?,?,0,0,?)",
                       (hashed(token), Access(self.db).policy(), hashlib.sha256(account.encode()).hexdigest()))
        return SimpleNamespace(base="https://example.test", settings=lambda: {"verified": True, "team": False, "token": token})

    def links(self):
        with self.db.connect() as db:
            return db.execute("SELECT link, source FROM research_links ORDER BY participant").fetchall()

    def test_same_account_computers_share_one_link_and_one_withdrawal_removes_both(self):
        first, second = self.verified("account-1"), self.verified("account-1")
        other = self.computer("other")
        for consent in (self.consent, other):
            consent.choose(True)
            for store in consent.collections.values():
                self.assertTrue(store.emit("answer", {"result": "pass", "card": "q1"}))
        self.assertFalse(self.consent.synchronize(identity=first)["errors"])
        self.assertFalse(other.synchronize(identity=second)["errors"])
        links = self.links()
        self.assertEqual(4, len(links))
        self.assertEqual(1, len(set(links)))
        self.assertEqual("account", links[0][1])
        target = self.root / "export.jsonl"
        self.db.export(str(target))
        text = target.read_text(encoding="utf-8")
        self.assertEqual({links[0][0]}, {json.loads(line)["research_link"] for line in text.splitlines()})
        with self.db.connect() as db:
            secret = [row[0] for row in db.execute("SELECT account_hash FROM identity_grants UNION SELECT account_key FROM research_accounts")]
        self.assertEqual(2, len(secret))
        self.assertFalse([value for value in secret if value in text])
        self.consent.withdraw()
        self.assertTrue(self.consent.synchronize(identity=first)["withdrawn"])
        with self.db.connect() as db:
            self.assertEqual(0, db.execute("SELECT count(*) FROM events").fetchone()[0])
            self.assertEqual(0, db.execute("SELECT count(*) FROM participants WHERE revoked=0").fetchone()[0])
            self.assertEqual([(None,)], db.execute("SELECT link FROM research_accounts").fetchall())
        self.assertEqual([], self.links())
        self.assertFalse(self.consent.path.with_name("research-link.json").exists())
        self.assertTrue(other.synchronize(identity=second)["errors"])
        self.assertTrue(other.settings()["withdraw_pending"])
        for store in other.collections.values():
            self.assertFalse(store.status()["enabled"])
            self.assertFalse(Path(store.path).exists())
        self.assertTrue(other.synchronize(identity=second)["withdrawn"])
        self.assertFalse(other.path.with_name("research-link.json").exists())

    def test_unverified_computer_links_its_own_courses_and_moves_to_the_account_after_verification(self):
        self.consent.choose(True)
        for store in self.collections.values():
            store.emit("answer", {"result": "pass"})
        self.assertFalse(self.consent.synchronize()["errors"])
        links = self.links()
        self.assertEqual([links[0], links[0]], links)
        self.assertEqual("device", links[0][1])
        identity = self.verified("account-1")
        self.assertFalse(self.consent.synchronize(identity=identity)["errors"])
        moved = self.links()
        self.assertEqual([moved[0], moved[0]], moved)
        self.assertEqual("account", moved[0][1])
        self.assertNotEqual(links[0][0], moved[0][0])
        with self.db.connect() as db:
            db.execute("DELETE FROM identity_grants")
        self.assertFalse(self.consent.synchronize(identity=identity)["errors"])
        self.assertEqual(moved, self.links())
        other = self.computer("other")
        other.choose(True)
        self.assertFalse(other.synchronize(identity=self.verified("account-2"))["errors"])
        self.assertEqual(2, len({link for link, source in self.links()}))

    def test_withdrawal_from_a_computer_that_never_sent_records_still_reaches_the_account(self):
        first = self.verified("account-1")
        other, late = self.computer("other"), self.computer("late")
        for consent in (self.consent, other, late):
            consent.choose(True)
        other.collections["ai"].emit("answer", {"result": "pass"})
        self.assertFalse(other.synchronize(identity=self.verified("account-1"))["errors"])
        old = self.links()[0][0]
        self.consent.withdraw()
        self.assertTrue(self.consent.synchronize(identity=first)["withdrawn"])
        with self.db.connect() as db:
            self.assertEqual(0, db.execute("SELECT count(*) FROM events").fetchone()[0])
            self.assertEqual(0, db.execute("SELECT count(*) FROM participants WHERE revoked=0").fetchone()[0])
        self.assertTrue(late.synchronize(identity=self.verified("account-1"))["errors"])
        self.assertTrue(late.settings()["withdraw_pending"])
        self.consent.choose(True)
        self.assertFalse(self.consent.synchronize(identity=first)["errors"])
        renewed = {link for link, source in self.links()}
        self.assertEqual(1, len(renewed))
        self.assertNotIn(old, renewed)

    def test_server_rejects_copied_links_wrong_proofs_and_links_on_old_receipts(self):
        from learning_data import privacy
        token = self.verified("account-1").settings()["token"]
        code, value = self.call("/v1/identity/research-link", {"consented_at": receipt()["at"]}, token)
        self.assertEqual(200, code)
        again = self.verified("account-1").settings()["token"]
        self.assertEqual(value, self.call("/v1/identity/research-link", {"consented_at": receipt()["at"]}, again)[1])
        other = self.verified("account-2").settings()["token"]
        self.assertNotEqual(value["link"], self.call("/v1/identity/research-link", {"consented_at": receipt()["at"]}, other)[1]["link"])
        self.assertEqual(400, self.call("/v1/identity/research-link", {"consented_at": "2026-11-23T12:00:00"}, token)[0])
        packet = {"participant": str(uuid.uuid4()), "notice": NOTICE, "registration_secret": secrets.token_hex(32), "consent": receipt()}
        self.assertEqual(403, self.call("/v1/enroll/open", dict(packet, research_link=value["link"]))[0])
        self.assertEqual(403, self.call("/v1/enroll/open", dict(packet, research_link=value["link"], research_proof="0" * 64))[0])
        self.assertEqual(403, self.call("/v1/research-link/withdraw", {"research_link": value["link"], "research_proof": "0" * 64})[0])
        old = dict(receipt(), policy="2026-11-13-v3", policy_hash=privacy.SUPPORTED_POLICIES["2026-11-13-v3"])
        self.assertEqual(400, self.call("/v1/enroll/open", dict(packet, consent=old, research_link=str(uuid.uuid4())))[0])
        self.assertEqual(200, self.call("/v1/enroll/open", dict(packet, research_link=value["link"], research_proof=value["proof"]))[0])
        self.assertEqual([(value["link"], "account")], self.links())

    def test_late_withdrawal_cleanup_preserves_a_new_consent_and_its_records(self):
        first, second = self.verified("account-1"), self.verified("account-1")
        other = self.computer("other")
        for consent, identity in ((self.consent, first), (other, second)):
            consent.choose(True)
            consent.collections["ai"].emit("answer", {"result": "pass"})
            self.assertFalse(consent.synchronize(identity=identity)["errors"])
        self.consent.withdraw()
        self.assertTrue(self.consent.synchronize(identity=first)["withdrawn"])
        self.consent.choose(True)
        self.collections["ai"].emit("answer", {"result": "pass", "card": "new-consent"})
        self.assertFalse(self.consent.synchronize(identity=first)["errors"])
        links = self.links()
        with self.db.connect() as db:
            events = db.execute("SELECT * FROM events ORDER BY participant, sequence").fetchall()
            withdrawn = db.execute("SELECT withdrawn FROM research_accounts").fetchone()
        self.assertTrue(other.synchronize(identity=second)["errors"])
        self.assertTrue(other.synchronize(identity=second)["withdrawn"])
        self.assertFalse(self.consent.synchronize(identity=first)["errors"])
        self.assertEqual(links, self.links())
        with self.db.connect() as db:
            self.assertEqual(events, db.execute("SELECT * FROM events ORDER BY participant, sequence").fetchall())
            self.assertEqual(withdrawn, db.execute("SELECT withdrawn FROM research_accounts").fetchone())

    def test_account_withdrawal_requires_consent_and_retry_does_not_advance_the_boundary(self):
        identity = self.verified("account-1")
        token = identity.settings()["token"]
        self.consent.choose(True)
        self.assertFalse(self.consent.synchronize(identity=identity)["errors"])
        data = {"consented_at": self.consent.settings()["receipt"]["at"]}
        self.assertEqual(400, self.call("/v1/identity/research-link", token=token, method="DELETE")[0])
        deleted = self.call("/v1/identity/research-link", data, token, "DELETE")
        with self.db.connect() as db:
            boundary = db.execute("SELECT withdrawn FROM research_accounts").fetchone()
        self.assertEqual((200, {"deleted": True, "withdrawn_at": boundary[0]}), deleted)
        self.consent.withdraw()
        self.assertTrue(self.consent.synchronize(identity=identity)["withdrawn"])
        self.consent.choose(True)
        self.assertFalse(self.consent.synchronize(identity=identity)["errors"])
        links = self.links()
        self.assertEqual((200, {"deleted": True, "withdrawn_at": boundary[0]}),
                         self.call("/v1/identity/research-link", data, token, "DELETE"))
        self.assertEqual(links, self.links())
        with self.db.connect() as db:
            self.assertEqual(boundary, db.execute("SELECT withdrawn FROM research_accounts").fetchone())

    def test_device_link_needs_a_separate_secret_and_does_not_export_it(self):
        self.consent.choose(True)
        self.assertFalse(self.consent.synchronize()["errors"])
        saved = self.consent._saved_research()
        self.assertIn("secret", saved)
        packet = {"participant": str(uuid.uuid4()), "notice": NOTICE,
                  "registration_secret": secrets.token_hex(32), "consent": receipt(), "research_link": saved["link"]}
        for extra in ({}, {"research_secret": "0" * 64}, {"research_proof": "0" * 64}):
            self.assertEqual(403, self.call("/v1/enroll/open", dict(packet, **extra))[0])
        self.assertEqual(403, self.call("/v1/research-link/withdraw", {"research_link": saved["link"]})[0])
        self.assertEqual(2, len(self.links()))
        destination = self.root / "device-export.jsonl"
        self.db.export(str(destination))
        text = destination.read_text(encoding="utf-8")
        self.assertIn(saved["link"], text)
        self.assertNotIn(saved["secret"], text)
        self.assertNotIn(hashlib.sha256(saved["secret"].encode()).hexdigest(), text)
        self.consent.withdraw()
        self.assertTrue(self.consent.synchronize()["withdrawn"])
        code, error = self.call("/v1/enroll/open", dict(packet, research_secret=saved["secret"]))
        self.assertEqual(401, code)
        self.assertEqual("revoked", error.get("code"))

    def test_rejected_identity_without_saved_proof_keeps_withdrawal_pending(self):
        identity = self.verified("account-1")
        other = self.computer("other")
        self.consent.choose(True)
        other.choose(True)
        self.assertFalse(other.synchronize(identity=self.verified("account-1"))["errors"])
        links = self.links()
        self.consent.withdraw()
        for failure in (CollectionError("unauthorized", status=401), CollectionError("forbidden", status=403),
                        CollectionError("unknown account", status=409), {}, {"deleted": False}):
            with self.subTest(failure=type(failure).__name__):
                self.consent.withdraw()
                with mock.patch.object(sharing, "request", side_effect=failure if isinstance(failure, Exception) else None,
                                       return_value=failure):
                    result = self.consent.synchronize(identity=identity)
                self.assertFalse(result["withdrawn"])
                self.assertTrue(result["errors"])
                self.assertTrue(self.consent.settings()["withdraw_pending"])
                self.assertEqual(links, self.links())
        self.assertTrue(self.consent.synchronize(identity=identity)["withdrawn"])
        self.assertEqual([], self.links())

    def test_device_withdrawal_limits_new_tombstones_but_keeps_existing_retries(self):
        import datetime
        self.consent.choose(True)
        self.assertFalse(self.consent.synchronize()["errors"])
        saved = self.consent._saved_research()
        now = datetime.datetime.now(datetime.timezone.utc)
        with self.db.connect() as db:
            db.executemany("INSERT INTO research_devices VALUES (?, ?, 1, ?)",
                           ((str(uuid.uuid4()), "0" * 64, now.isoformat()) for _ in range(9999)))
        unknown = {"research_link": str(uuid.uuid4()), "research_secret": secrets.token_hex(32)}
        self.assertEqual(429, self.call("/v1/research-link/withdraw", unknown)[0])
        with self.db.connect() as db:
            self.assertEqual(10000, db.execute("SELECT count(*) FROM research_devices").fetchone()[0])
            self.assertIsNone(db.execute("SELECT 1 FROM research_devices WHERE link=?", (unknown["research_link"],)).fetchone())
        self.consent.withdraw()
        self.assertTrue(self.consent.synchronize()["withdrawn"])
        retry = {"research_link": saved["link"], "research_secret": saved["secret"]}
        self.assertEqual((200, {"deleted": True}), self.call("/v1/research-link/withdraw", retry))
        with self.db.connect() as db:
            db.execute("UPDATE research_devices SET created=?", ((now-datetime.timedelta(days=2)).isoformat(),))
        self.assertEqual((200, {"deleted": True}), self.call("/v1/research-link/withdraw", unknown))
        self.assertEqual((200, {"deleted": True}), self.call("/v1/research-link/withdraw", unknown))
        packet = {"participant": str(uuid.uuid4()), "notice": NOTICE,
                  "registration_secret": secrets.token_hex(32), "consent": receipt(), **unknown}
        code, error = self.call("/v1/enroll/open", packet)
        self.assertEqual(401, code)
        self.assertEqual("revoked", error.get("code"))

    def test_saved_proof_finishes_withdrawal_after_identity_key_is_revoked(self):
        identity = self.verified("account-1")
        self.consent.choose(True)
        self.assertFalse(self.consent.synchronize(identity=identity)["errors"])
        with self.db.connect() as db:
            db.execute("DELETE FROM identity_grants")
        self.consent.withdraw()
        normal = self.transport
        def missing_ack(base, path, *args, **kwargs):
            if path == "/v1/research-link/withdraw":
                return {}
            return normal(base, path, *args, **kwargs)
        with mock.patch.object(sharing, "request", missing_ack):
            self.assertFalse(self.consent.synchronize(identity=identity)["withdrawn"])
        self.assertTrue(self.consent.settings()["withdraw_pending"])
        self.assertTrue(self.consent.path.with_name("research-link.json").exists())
        self.assertTrue(self.consent.synchronize(identity=identity)["withdrawn"])

    def test_paused_courses_detect_account_withdrawal_with_or_without_identity_key(self):
        for keep_identity in (True, False):
            with self.subTest(keep_identity=keep_identity):
                self.setUp()
                first, second = self.verified("account-1"), self.verified("account-1")
                other = self.computer("other")
                for consent, identity in ((self.consent, first), (other, second)):
                    consent.choose(True)
                    self.assertFalse(consent.synchronize(identity=identity)["errors"])
                for store in other.collections.values():
                    store.set_enabled(False)
                self.consent.withdraw()
                self.assertTrue(self.consent.synchronize(identity=first)["withdrawn"])
                self.assertTrue(other.synchronize(identity=second if keep_identity else None)["errors"])
                self.assertTrue(other.settings()["withdraw_pending"])
                self.assertTrue(all(not Path(store.path).exists() for store in other.collections.values()))
                self.assertTrue(other.synchronize(identity=second if keep_identity else None)["withdrawn"])

    def test_lost_account_delete_ack_retries_only_the_original_consent(self):
        identity = self.verified("account-1")
        other = self.computer("other")
        self.consent.choose(True)
        original_at = self.consent.settings()["receipt"]["at"]
        other.choose(True)
        self.assertFalse(other.synchronize(identity=self.verified("account-1"))["errors"])
        self.consent.choose(False)
        self.assertEqual(original_at, self.consent.settings()["receipt"]["at"])
        self.consent.withdraw()
        normal = self.transport
        def lost_ack(base, path, *args, **kwargs):
            result = normal(base, path, *args, **kwargs)
            if path == "/v1/identity/research-link" and kwargs.get("method") == "DELETE":
                raise CollectionError("lost acknowledgement")
            return result
        with mock.patch.object(sharing, "request", lost_ack):
            self.assertFalse(self.consent.synchronize(identity=identity)["withdrawn"])
        with self.db.connect() as db:
            boundary = db.execute("SELECT withdrawn FROM research_accounts").fetchone()
        renewed = self.computer("renewed")
        renewed_identity = self.verified("account-1")
        renewed.choose(True)
        self.assertTrue(renewed.synchronize(identity=renewed_identity)["errors"])
        self.assertTrue(renewed.synchronize(identity=renewed_identity)["withdrawn"])
        renewed.choose(True)
        renewed.collections["ai"].emit("answer", {"result": "pass"})
        self.assertFalse(renewed.synchronize(identity=self.verified("account-1"))["errors"])
        links = self.links()
        self.assertTrue(self.consent.synchronize(identity=identity)["withdrawn"])
        self.assertEqual(links, self.links())
        with self.db.connect() as db:
            self.assertEqual(boundary, db.execute("SELECT withdrawn FROM research_accounts").fetchone())
            self.assertEqual(1, db.execute("SELECT count(*) FROM events WHERE json_extract(payload,'$.kind')='answer'").fetchone()[0])

    def test_legacy_device_link_moves_with_existing_participant_credentials_and_keeps_events(self):
        from learning_data.privacy import save
        self.consent.choose(True)
        self.collections["ai"].emit("answer", {"result": "pass"})
        self.assertFalse(self.consent.synchronize()["errors"])
        old = self.consent._saved_research()["link"]
        with self.db.connect() as db:
            db.execute("DELETE FROM research_devices")
            events = db.execute("SELECT * FROM events ORDER BY participant, sequence").fetchall()
        save(self.consent.path.with_name("research-link.json"), {"link": old})
        tokens = [sharing.Sharing(store).settings()["token"] for store in self.collections.values()]
        self.assertFalse(self.consent.synchronize()["errors"])
        self.assertNotEqual(old, self.consent._saved_research()["link"])
        self.assertEqual(tokens, [sharing.Sharing(store).settings()["token"] for store in self.collections.values()])
        with self.db.connect() as db:
            self.assertEqual(events, db.execute("SELECT * FROM events ORDER BY participant, sequence").fetchall())
        self.assertEqual(1, len({link for link, source in self.links()}))

    def test_legacy_device_link_does_not_grant_group_deletion_or_secret_registration(self):
        self.consent.choose(True)
        self.assertFalse(self.consent.synchronize()["errors"])
        old = self.consent._saved_research()["link"]
        with self.db.connect() as db:
            db.execute("DELETE FROM research_devices")
        packet = {"participant": str(uuid.uuid4()), "notice": NOTICE, "registration_secret": secrets.token_hex(32),
                  "consent": receipt(), "research_link": old, "research_secret": secrets.token_hex(32)}
        self.assertEqual(403, self.call("/v1/enroll/open", packet)[0])
        first, second = [sharing.Sharing(store).settings() for store in self.collections.values()]
        self.assertEqual(200, self.call("/v1/me", token=first["token"], method="DELETE")[0])
        self.assertEqual([(old, "device")], self.links())
        with self.db.connect() as db:
            self.assertEqual((0,), db.execute("SELECT revoked FROM participants WHERE participant=?", (second["participant"],)).fetchone())

    def test_research_status_requires_proof_and_does_not_expose_account_values(self):
        identity = self.verified("account-1")
        self.consent.choose(True)
        self.assertFalse(self.consent.synchronize(identity=identity)["errors"])
        saved = self.consent._saved_research()
        for proof in (None, "0" * 64):
            self.assertEqual(403, self.call("/v1/research-link/status", {"research_link": saved["link"], "research_proof": proof})[0])
        packet = {"research_link": saved["link"], "research_proof": saved["proof"]}
        self.assertEqual((200, {"active": True}), self.call("/v1/research-link/status", packet))
        self.consent.withdraw()
        self.assertTrue(self.consent.synchronize(identity=identity)["withdrawn"])
        code, result = self.call("/v1/research-link/status", packet)
        self.assertEqual(401, code)
        self.assertEqual("revoked", result.get("code"))

    def test_decline_does_not_collect_register_or_upload(self):
        self.consent.choose(False)
        self.assertFalse(self.consent.needs_choice())
        for store in self.collections.values():
            self.assertFalse(store.emit("answer", {"result": "pass"}))
            self.assertFalse(Path(store.path).exists())
        self.assertEqual(0, self.consent.synchronize()["sent"])
        with self.db.connect() as db:
            self.assertEqual(0, db.execute("SELECT count(*) FROM participants").fetchone()[0])

    def test_current_consent_uploads_only_new_records_without_answer_body(self):
        for store in self.collections.values():
            store.set_enabled(True)
            store.emit("answer", {"response": "OLD PRIVATE ANSWER", "result": "fail"})
        self.consent.choose(True)
        for store in self.collections.values():
            store.emit("answer", {"response": "NEW PRIVATE ANSWER", "result": "pass"})
        result = self.consent.synchronize()
        self.assertFalse(result["errors"])
        self.assertEqual(0, self.consent.synchronize()["sent"])
        with self.db.connect() as db:
            rows = [json.loads(r[0]) for r in db.execute("SELECT payload FROM events")]
            self.assertEqual(2, sum(row["kind"] == "answer" for row in rows))
            self.assertNotIn("PRIVATE ANSWER", json.dumps(rows))
            self.assertEqual(0, db.execute("SELECT count(*) FROM submission_accounts").fetchone()[0])

    def test_pausing_python_does_not_stop_ai_automatic_upload(self):
        self.consent.choose(True)
        self.collections["python"].set_enabled(False)
        self.collections["ai"].emit("answer", {"result": "pass"})
        self.assertFalse(self.consent.synchronize()["errors"])
        with self.db.connect() as db:
            self.assertEqual(1, db.execute("SELECT count(*) FROM events WHERE track='ai' AND json_extract(payload, '$.kind')='answer'").fetchone()[0])
            self.assertEqual(0, db.execute("SELECT count(*) FROM events WHERE track='python'").fetchone()[0])

    def test_quota_rejection_keeps_cursor_and_retries_without_duplicate_after_lost_ack(self):
        self.consent.choose(True)
        self.assertFalse(self.consent.synchronize()["errors"])
        store = self.collections["ai"]
        share = sharing.Sharing(store)
        participant = share.settings()["participant"]
        confirmed = share.settings()["sequence"]
        with self.db.connect() as db:
            _, used = usage(db, participant)
            self.db.storage_limit(db, participant, 16 * 1024 * 1024 + 1 - used)

        store.emit("answer", {"result": "pass"})
        pending = store.snapshot(after=confirmed)[1:]
        self.assertEqual(1, len(pending))

        def stored():
            with self.db.connect() as db:
                return db.execute("SELECT count(*) FROM events WHERE event_id=?", (pending[0]["event_id"],)).fetchone()[0]

        with mock.patch.object(app, "MAX_PARTICIPANT_BYTES", used):
            self.assertIn("보관량", self.consent.synchronize()["errors"][0])
        self.assertEqual(0, stored())
        self.assertEqual(confirmed, share.settings()["sequence"])
        self.assertEqual(pending, store.snapshot(after=confirmed)[1:])

        def lose_ack(base, path, *args, **kwargs):
            result = self.transport(base, path, *args, **kwargs)
            if path == "/v1/events":
                raise CollectionError("시험에서 저장 확인 응답을 놓쳤습니다.")
            return result

        with mock.patch.object(sharing, "request", side_effect=lose_ack):
            self.assertTrue(self.consent.synchronize()["errors"])
        self.assertEqual(1, stored())
        self.assertEqual(confirmed, share.settings()["sequence"])
        reopened = Consent(self.collections, "https://example.test")
        self.assertEqual({"sent": 1, "errors": []}, reopened.synchronize())
        self.assertEqual(1, stored())
        self.assertEqual(pending[0]["sequence"], share.settings()["sequence"])
        self.assertEqual({"sent": 0, "errors": []}, reopened.synchronize())

    def test_offline_withdraw_stops_immediately_and_retries_remote_delete(self):
        self.consent.choose(True)
        self.consent.synchronize()
        old = [sharing.Sharing(store).settings()["token"] for store in self.collections.values()]
        self.consent.withdraw()
        with mock.patch.object(sharing, "request", side_effect=CollectionError("offline")):
            self.assertTrue(self.consent.synchronize()["errors"])
        self.assertTrue(self.consent.settings()["withdraw_pending"])
        for store in self.collections.values():
            self.assertFalse(store.status()["enabled"])
            self.assertFalse(Path(store.path).exists())
        self.assertTrue(self.consent.synchronize()["withdrawn"])
        self.assertFalse(self.consent.settings()["withdraw_pending"])
        with self.db.connect() as db:
            self.assertEqual(0, db.execute("SELECT count(*) FROM events").fetchone()[0])
        for token in old:
            self.assertEqual(401, self.call("/v1/events", {}, token)[0])
        self.consent.choose(True)
        self.assertFalse(self.consent.synchronize()["errors"])

    def test_registration_retries_require_private_seed_and_explicit_current_receipt(self):
        packet = {"participant": str(uuid.uuid4()), "notice": NOTICE,
                  "registration_secret": secrets.token_hex(32), "consent": receipt()}
        code, first = self.call("/v1/enroll/open", packet)
        self.assertEqual(200, code)
        self.assertEqual(first, self.call("/v1/enroll/open", packet)[1])
        self.assertEqual(409, self.call("/v1/enroll/open", dict(packet, registration_secret=secrets.token_hex(32)))[0])
        self.assertEqual(400, self.call("/v1/enroll/open", dict(packet, consent={}))[0])
        with mock.patch.dict(os.environ, {"STUDY_OPEN_REGISTRATION": "0"}):
            self.assertEqual(503, self.call("/v1/enroll/open", packet)[0])

    def test_local_delete_failure_stops_every_track_and_keeps_retry_pending(self):
        self.consent.choose(True)
        self.consent.synchronize()
        with mock.patch.object(self.collections["python"], "delete", side_effect=CollectionError("locked")):
            self.consent.withdraw()
            self.assertTrue(all(not store.status()["enabled"] for store in self.collections.values()))
            self.assertTrue(self.consent.synchronize()["errors"])
            self.assertTrue(self.consent.settings()["withdraw_pending"])
        self.assertTrue(self.consent.synchronize()["withdrawn"])
        self.assertFalse(self.consent.settings()["withdraw_pending"])

    def test_lost_registration_ack_can_be_withdrawn_without_creating_another_account(self):
        self.consent.choose(True)
        normal = self.transport
        failed = []
        def lost(base, path, *args, **kwargs):
            value = normal(base, path, *args, **kwargs)
            if path == "/v1/enroll/open" and not failed:
                failed.append(True)
                raise CollectionError("lost acknowledgement")
            return value
        with mock.patch.object(sharing, "request", lost):
            self.assertTrue(self.consent.synchronize()["errors"])
        self.consent.withdraw()
        self.assertTrue(self.consent.synchronize()["withdrawn"])
        with self.db.connect() as db:
            self.assertEqual(0, db.execute("SELECT count(*) FROM participants WHERE revoked=0").fetchone()[0])
        self.consent.choose(True)
        self.assertFalse(self.consent.synchronize()["errors"])

    def test_failed_enable_or_consent_save_does_not_leave_collection_running(self):
        with mock.patch.object(self.collections["ai"], "set_enabled", side_effect=CollectionError("locked")):
            with self.assertRaises(CollectionError):
                self.consent.choose(True)
        self.assertTrue(all(not store.status()["enabled"] for store in self.collections.values()))
        with mock.patch("aiprep.privacy.save", side_effect=OSError("disk")):
            with self.assertRaises(OSError):
                self.consent.choose(True)
        self.assertTrue(all(not store.status()["enabled"] for store in self.collections.values()))

    def test_declining_a_new_notice_pauses_without_unconfirmed_deletion(self):
        self.consent.choose(True)
        store = self.collections["ai"]
        store.emit("answer", {"result": "pass"})
        self.consent.synchronize()
        config = sharing.Sharing(store).settings()
        rows = store.status()["events"]
        self.consent.choose(False)
        self.assertFalse(self.consent.settings().get("withdraw_pending", False))
        self.assertTrue(all(not item.status()["enabled"] for item in self.collections.values()))
        self.assertEqual(rows, store.status()["events"])
        self.assertEqual(config, sharing.Sharing(store).settings())
        self.assertEqual(0, self.consent.synchronize()["sent"])
        with self.db.connect() as db:
            self.assertGreater(db.execute("SELECT count(*) FROM events").fetchone()[0], 0)
        self.consent.withdraw()
        self.assertTrue(self.consent.synchronize()["withdrawn"])

    def test_reconsent_keeps_connection_and_skips_previously_held_records(self):
        self.consent.choose(True)
        self.consent.synchronize()
        store = self.collections["ai"]
        config = sharing.Sharing(store).settings()
        store.emit("answer", {"result": "fail"})
        held = store.latest_sequence()
        self.consent.choose(False)
        self.consent.choose(True)
        store.emit("answer", {"result": "pass"})
        self.assertFalse(self.consent.synchronize()["errors"])
        new = sharing.Sharing(store).settings()
        self.assertEqual(config["token"], new["token"])
        self.assertEqual(self.consent.settings()["receipt"], new["consent_receipt"])
        with self.db.connect() as db:
            rows = [json.loads(row[0]) for row in db.execute("SELECT payload FROM events WHERE track='ai'")]
        answers = [row for row in rows if row["kind"] == "answer"]
        self.assertEqual(["pass"], [row["data"]["result"] for row in answers])
        self.assertTrue(all(row["sequence"] > held for row in answers))

    def test_confirmed_server_revocation_stops_all_local_collection(self):
        self.consent.choose(True)
        self.consent.synchronize()
        store = self.collections["python"]
        config = sharing.Sharing(store).settings()
        self.db.remove(config["participant"])
        store.emit("answer", {"result": "pass"})
        self.assertTrue(self.consent.synchronize()["errors"])
        self.assertTrue(self.consent.settings()["withdraw_pending"])
        self.assertTrue(all(not item.status()["enabled"] for item in self.collections.values()))
        self.assertTrue(self.consent.synchronize()["withdrawn"])

    def test_empty_first_run_profile_does_not_remind_public_submission(self):
        self.consent.choose(False)
        folder = self.repo / "submissions/tester"
        folder.mkdir(parents=True)
        (folder / "profile.json").write_text('{"rounds": [], "attempts": []}')
        client = Client(str(self.repo), "tester", self.collections)
        self.assertFalse(client.pending()["pending"])

    def test_public_submission_can_connect_without_research_consent(self):
        self.consent.choose(False)
        client = Client(str(self.repo), "tester", self.collections)
        client.transport = self.transport
        client.connect_open("https://example.test")
        config = client.settings()
        self.assertNotIn(uuid.UUID(config["participant"]).hex[:10], config["display_id"])
        client.connect_open("https://example.test")
        with self.db.connect() as db:
            self.assertEqual(1, db.execute("SELECT count(*) FROM submission_accounts").fetchone()[0])
            self.assertEqual(0, db.execute("SELECT count(*) FROM submission_collections").fetchone()[0])
            self.assertEqual(0, db.execute("SELECT count(*) FROM events").fetchone()[0])
        row = {"participant": config["participant"], "track": "python", "format": 1,
               "event_id": str(uuid.uuid4()), "sequence": 1, "at": stamp(), "kind": "answer", "data": {"result": "pass"}}
        packet = {"participant": config["participant"], "notice": NOTICE, "format": 1, "track": "python", "events": [row]}
        self.assertEqual(403, self.call("/v1/events", packet, config["token"])[0])
