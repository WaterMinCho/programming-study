"""계정별 당일 신호의 선택·날짜·재전송·철회를 확인함."""
import datetime
import json
import tempfile
import threading
import unittest
from unittest import mock

import study
from learning_data.collection import CollectionError
from learning_data.daily_study import DailyStudy, KST
from learning_data.identity import Identity
from learning_data.privacy import save


class DailyStudyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.identity = Identity(study.ROOT, "tester", home=self.tmp.name)
        self.identity.save({"verified": True, "team": False, "token": "a" * 64})
        self.daily = DailyStudy(self.identity)
        self.day = datetime.datetime.now(KST).date().isoformat()
        self.store = mock.Mock()
        self.stores = {"ai": self.store}

    def marker(self):
        return {"date": self.day, "identity": self.daily.fingerprint(), "choice": self.daily.settings()["choice"]}

    def test_default_off_and_explicit_choice_does_not_send_prior_answers(self):
        with mock.patch("learning_data.daily_study.request") as request:
            self.daily.synchronize(self.stores, allowed=True)
            self.assertFalse(self.daily.enabled())
            self.daily.choose(True)
            self.store.daily_study.return_value = {}
            self.daily.synchronize(self.stores, allowed=True)
            request.assert_not_called()

    def test_current_grade_is_sent_once_and_only_date_and_existing_nonce_leave(self):
        self.daily.choose(True)
        nonce = self.identity.installation_nonce()
        self.store.daily_study.return_value = self.marker()
        with mock.patch("learning_data.daily_study.request", return_value={"eligible": True, "date": self.day}) as request:
            self.daily.synchronize(self.stores, allowed=True)
            self.daily.synchronize(self.stores, allowed=True)
            request.assert_called_once()
            self.assertEqual({"date": self.day, "accepted": True, "nonce": nonce}, request.call_args.args[2])
        saved = self.daily.path.read_text()
        self.assertNotIn("a" * 64, saved)
        self.assertNotIn(nonce, saved)

    def test_wrong_account_day_or_choice_and_stopped_collection_are_not_sent(self):
        self.daily.choose(True)
        marker = self.marker()
        with mock.patch("learning_data.daily_study.request") as request:
            for change in ({"date": "2000-01-01"}, {"date": "2099-01-01"}, {"identity": "b" * 64}, {"choice": "previous"}):
                self.store.daily_study.return_value = dict(marker, **change)
                self.daily.synchronize(self.stores, allowed=True)
            self.store.daily_study.return_value = marker
            self.daily.synchronize(self.stores, allowed=False)
            self.daily.synchronize(self.stores, allowed=True, canceled=lambda: True)
            self.identity.save({"verified": True, "team": False, "token": "b" * 64})
            self.daily.synchronize(self.stores, allowed=True)
            self.assertFalse(self.daily.enabled())
            request.assert_not_called()

    def test_network_failure_retries_and_account_switch_does_not_reuse_marker(self):
        self.daily.choose(True)
        self.store.daily_study.return_value = self.marker()
        with mock.patch("learning_data.daily_study.request", side_effect=[CollectionError("offline"), {"eligible": True, "date": self.day}]) as request:
            with self.assertRaises(CollectionError):
                self.daily.synchronize(self.stores, allowed=True)
            self.assertNotIn("sent_date", self.daily.settings())
            self.daily.synchronize(self.stores, allowed=True)
            self.assertEqual(2, request.call_count)

    def test_disable_deletes_even_without_research_permission_and_waits_for_confirmation(self):
        self.daily.choose(True)
        old_choice = self.daily.settings()["choice"]
        self.daily.choose(False)
        self.assertFalse(self.daily.enabled())
        with self.assertRaises(CollectionError):
            self.daily.choose(True)
        with mock.patch("learning_data.daily_study.request", return_value={"eligible": True, "deleted": True}) as request:
            self.assertEqual("deleted", self.daily.synchronize({}, allowed=False))
            self.assertEqual("DELETE", request.call_args.kwargs["method"])
            self.assertEqual({}, request.call_args.args[2])
        self.assertFalse(self.daily.settings()["delete_pending"])
        self.assertFalse(self.identity.path.with_name("identity-device.json").exists())
        self.daily.choose(True)
        self.assertNotEqual(old_choice, self.daily.settings()["choice"])

    def test_old_server_or_unlinked_grant_never_mark_the_signal_as_sent(self):
        self.daily.choose(True)
        self.store.daily_study.return_value = self.marker()
        with mock.patch("learning_data.daily_study.request", return_value={"eligible": False, "date": self.day}):
            self.daily.synchronize(self.stores, allowed=True)
        self.assertNotIn("sent_date", self.daily.settings())
        with mock.patch("learning_data.daily_study.request", side_effect=CollectionError("old server", status=404)):
            with self.assertRaises(CollectionError):
                self.daily.synchronize(self.stores, allowed=True)
        self.assertNotIn("sent_date", self.daily.settings())

    def test_consent_change_during_request_keeps_delete_pending(self):
        self.daily.choose(True)
        self.store.daily_study.return_value = self.marker()
        def response(*args, **kwargs):
            self.daily.choose(False)
            return {"eligible": True, "date": self.day}
        with mock.patch("learning_data.daily_study.request", side_effect=response):
            self.daily.synchronize(self.stores, allowed=True)
        self.assertTrue(self.daily.settings()["delete_pending"])
        self.assertNotIn("sent_date", self.daily.settings())

    def test_disable_waits_for_response_save_in_another_instance(self):
        self.daily.choose(True)
        self.store.daily_study.return_value = self.marker()
        other = DailyStudy(self.identity)
        saving, release = threading.Event(), threading.Event()
        choosing, chosen = threading.Event(), threading.Event()
        failures = []

        def delayed_save(path, value):
            if value.get("sent_date") == self.day:
                saving.set()
                if not release.wait(3):
                    raise AssertionError("응답 저장 대기를 끝내지 못함")
            save(path, value)

        def synchronize():
            try:
                self.daily.synchronize(self.stores, allowed=True)
            except BaseException as error:
                failures.append(error)

        def disable():
            choosing.set()
            try:
                other.choose(False)
            except BaseException as error:
                failures.append(error)
            finally:
                chosen.set()

        worker, chooser = threading.Thread(target=synchronize), threading.Thread(target=disable)
        with mock.patch("learning_data.daily_study.save", side_effect=delayed_save), \
                mock.patch("learning_data.daily_study.request", return_value={"eligible": True, "date": self.day}):
            worker.start()
            try:
                self.assertTrue(saving.wait(3))
                chooser.start()
                self.assertTrue(choosing.wait(3))
                self.assertFalse(chosen.wait(0.05))
            finally:
                release.set()
                worker.join(3)
                if chooser.ident is not None:
                    chooser.join(3)
        self.assertFalse(worker.is_alive())
        self.assertFalse(chooser.is_alive())
        self.assertEqual([], failures)
        self.assertFalse(self.daily.enabled())
        self.assertTrue(self.daily.settings()["delete_pending"])
        self.assertNotIn("sent_date", self.daily.settings())

    def test_network_wait_does_not_lock_out_disable_in_another_instance(self):
        self.daily.choose(True)
        self.store.daily_study.return_value = self.marker()
        entered, disabled = threading.Event(), threading.Event()
        failures = []

        def response(*args, **kwargs):
            entered.set()
            if not disabled.wait(3):
                raise AssertionError("통신 대기가 선택 변경을 막음")
            return {"eligible": True, "date": self.day}

        def synchronize():
            try:
                self.daily.synchronize(self.stores, allowed=True)
            except BaseException as error:
                failures.append(error)

        def disable():
            try:
                DailyStudy(self.identity).choose(False)
            except BaseException as error:
                failures.append(error)
            finally:
                disabled.set()

        worker, chooser = threading.Thread(target=synchronize), threading.Thread(target=disable)
        with mock.patch("learning_data.daily_study.request", side_effect=response):
            worker.start()
            try:
                self.assertTrue(entered.wait(3))
                chooser.start()
                self.assertTrue(disabled.wait(3))
            finally:
                disabled.set()
                worker.join(3)
                if chooser.ident is not None:
                    chooser.join(3)
        self.assertFalse(worker.is_alive())
        self.assertFalse(chooser.is_alive())
        self.assertEqual([], failures)
        self.assertFalse(self.daily.enabled())
        self.assertTrue(self.daily.settings()["delete_pending"])

    def test_account_switch_preserves_deletion_without_token_and_retries_on_return(self):
        self.daily.choose(True)
        fingerprint_a = self.daily.fingerprint()
        self.daily.choose(False)
        with mock.patch("learning_data.daily_study.request", side_effect=CollectionError("offline")):
            with self.assertRaises(CollectionError):
                self.daily.synchronize({}, allowed=False)
        self.identity.save({"verified": True, "team": False, "token": "b" * 64})
        self.daily.choose(True)
        choice_b = self.daily.settings()["choice"]
        pending = [{"identity": fingerprint_a, "date": self.day}]
        self.assertEqual(pending, self.daily.settings()["unresolved_deletions"])
        with mock.patch("learning_data.daily_study.request") as request:
            self.daily.synchronize({}, allowed=False)
            request.assert_not_called()
        saved = self.daily.path.read_text()
        for token in ("a" * 64, "b" * 64):
            self.assertNotIn(token, saved)

        self.identity.save({"verified": True, "team": False, "token": "a" * 64})
        self.assertEqual(fingerprint_a, self.daily.settings()["identity"])
        self.assertTrue(self.daily.settings()["delete_pending"])
        self.assertFalse(self.daily.enabled())
        with self.assertRaises(CollectionError):
            self.daily.choose(True)
        with mock.patch("learning_data.daily_study.request", return_value={"eligible": True, "deleted": True}) as request:
            self.assertEqual("deleted", self.daily.synchronize({}, allowed=False))
            self.assertEqual("a" * 64, request.call_args.kwargs["token"])
            self.assertEqual("DELETE", request.call_args.kwargs["method"])
        self.assertEqual([], self.daily.settings()["unresolved_deletions"])
        self.identity.save({"verified": True, "team": False, "token": "b" * 64})
        self.assertTrue(self.daily.enabled())
        self.assertEqual(choice_b, self.daily.settings()["choice"])

    def test_previous_day_deletion_stays_unconfirmed_without_deleting_new_day(self):
        self.daily.choose(False)
        pending = [{"identity": self.daily.fingerprint(), "date": self.day}]
        tomorrow = datetime.datetime.now(KST) + datetime.timedelta(days=1)
        with mock.patch("learning_data.daily_study.datetime.datetime") as clock, \
                mock.patch("learning_data.daily_study.request") as request:
            clock.now.return_value = tomorrow
            self.assertIsNone(self.daily.synchronize({}, allowed=False))
            self.assertFalse(self.daily.settings()["delete_pending"])
            self.assertEqual(pending, self.daily.settings()["unresolved_deletions"])
            self.daily.choose(True)
            self.assertTrue(self.daily.enabled())
            self.assertEqual(pending, self.daily.settings()["unresolved_deletions"])
            request.assert_not_called()

    def test_legacy_pending_date_is_preserved_on_account_switch(self):
        self.daily.choose(False)
        old = json.loads(self.daily.path.read_text())
        old.pop("delete_date")
        old.pop("unresolved_deletions")
        save(self.daily.path, old)
        self.identity.save({"verified": True, "team": False, "token": "b" * 64})
        self.daily.choose(True)
        self.assertEqual([{"identity": old["identity"], "date": self.day}], self.daily.settings()["unresolved_deletions"])

    def test_invalid_delete_response_never_confirms_or_drops_pending(self):
        self.daily.choose(False)
        pending = self.daily.settings()["unresolved_deletions"]
        for result in ({"eligible": False, "deleted": False}, {"eligible": True, "deleted": False}):
            with self.subTest(result=result), mock.patch("learning_data.daily_study.request", return_value=result):
                with self.assertRaises(CollectionError):
                    self.daily.synchronize({}, allowed=False)
                self.assertEqual(pending, self.daily.settings()["unresolved_deletions"])
                self.assertTrue(self.daily.settings()["delete_pending"])

    def test_alternate_server_cannot_receive_identity_or_study_signal(self):
        self.daily.choose(True)
        self.store.daily_study.return_value = self.marker()
        self.identity.base = "https://other.example"
        with mock.patch("learning_data.daily_study.request") as request:
            self.daily.synchronize(self.stores, allowed=True)
            request.assert_not_called()


class TodaySummaryTest(unittest.TestCase):
    def test_summary_rejects_invalid_counts_date_and_partial_coverage(self):
        with tempfile.TemporaryDirectory() as home:
            identity = Identity(study.ROOT, "tester", home=home)
            identity.save({"verified": True, "team": True, "token": "a" * 64})
            rows = [{"at": "2026-11-16T12:00:00+09:00", "ai": 0, "python": 0} for _ in range(7)]
            base = dict(days=7, total=0, period_total=0, undated=0, series=rows,
                        installations=4, period_installations=0, accounts=3, period_accounts=0,
                        as_of="2026-11-16T12:00:00+09:00")
            today = dict(date="2026-11-16", accounts=1, eligible_accounts=2, authenticated_accounts=3, coverage="partial")
            with mock.patch("learning_data.identity.request", return_value=dict(base, today=today)) as request:
                self.assertEqual(today, identity.summary(7)["today"])
                request.return_value = dict(base, today=dict(today, accounts=3, eligible_accounts=1))
                self.assertEqual(3, identity.summary(7)["today"]["accounts"])
                for change in ({"date": "2026-11-15"}, {"accounts": True}, {"accounts": 4},
                               {"coverage": "all"}, {"eligible_accounts": -1}, {"authenticated_accounts": 4}):
                    request.return_value = dict(base, today=dict(today, **change))
                    with self.assertRaises(CollectionError):
                        identity.summary(7)
