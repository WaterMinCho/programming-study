"""인증 계정의 당일 채점 표식과 전송을 확인함. 학습 기록 제공 동의와는 따로 동작함."""
import datetime
import json
import tempfile
import threading
import unittest
from unittest import mock

import study
from learning_data.collection import CollectionError
from learning_data.daily_study import DailyStudy, KST, VERSION
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

    def sent(self):
        return {"eligible": True, "date": self.day}

    def test_nothing_is_sent_before_a_grade_today(self):
        # 예전에는 기본 꺼짐과 선택을 확인했음. 선택이 없어져 채점 표식이 없으면 보내지 않는지 봄.
        with mock.patch("learning_data.daily_study.request") as request:
            self.daily.synchronize()
            self.assertFalse(self.daily.due())
            request.assert_not_called()

    def test_current_grade_is_sent_once_and_only_date_and_existing_nonce_leave(self):
        nonce = self.identity.installation_nonce()
        self.assertTrue(self.daily.mark())
        self.assertFalse(self.daily.mark())
        self.assertTrue(self.daily.due())
        with mock.patch("learning_data.daily_study.request", return_value=self.sent()) as request:
            self.daily.synchronize()
            self.daily.synchronize()
            request.assert_called_once()
            self.assertEqual({"date": self.day, "accepted": True, "nonce": nonce}, request.call_args.args[2])
            self.assertEqual("POST", request.call_args.kwargs["method"])
            self.assertEqual("/v1/identity/study-activity", request.call_args.args[1])
        self.assertFalse(self.daily.due())
        saved = self.daily.path.read_text()
        self.assertNotIn("a" * 64, saved)
        self.assertNotIn(nonce, saved)
        self.assertEqual({"version", "date", "graded", "sent"}, set(json.loads(saved)))

    def test_unverified_or_canceled_or_other_account_is_not_sent(self):
        # 예전에는 다른 날짜·선택 구분값·수집 중지도 확인했음. 표식에 선택 구분값이 없어져 계정과 취소만 봄.
        with tempfile.TemporaryDirectory() as home:
            unverified = DailyStudy(Identity(study.ROOT, "tester", home=home))
            self.assertFalse(unverified.mark())
            self.assertFalse(unverified.path.exists())
            with mock.patch("learning_data.daily_study.request") as request:
                unverified.synchronize()
                request.assert_not_called()
        self.daily.mark()
        with mock.patch("learning_data.daily_study.request") as request:
            self.daily.synchronize(canceled=lambda: True)
            self.identity.save({"verified": True, "team": False, "token": "b" * 64})
            self.daily.synchronize()
            self.assertFalse(self.daily.due())
            request.assert_not_called()

    def test_network_failure_retries(self):
        self.daily.mark()
        with mock.patch("learning_data.daily_study.request", side_effect=[CollectionError("offline"), self.sent()]) as request:
            with self.assertRaises(CollectionError):
                self.daily.synchronize()
            self.assertTrue(self.daily.due())
            self.daily.synchronize()
            self.assertEqual(2, request.call_count)
        self.assertFalse(self.daily.due())

    def test_never_sends_a_delete_request(self):
        # 예전에는 선택을 끄면 삭제 요청을 보냈음. 선택이 없어져 삭제 요청을 보내지 않음.
        self.daily.mark()
        with mock.patch("learning_data.daily_study.request", return_value=self.sent()) as request:
            self.daily.synchronize()
            self.daily.synchronize()
        self.assertEqual(["POST"], [call.kwargs["method"] for call in request.call_args_list])

    def test_unlinked_grant_is_not_sent_again_that_day(self):
        # 예전에는 eligible:false 뒤에도 due 가 참으로 남아 1분마다 다시 보냈음. 그날은 다시 보내지 않아야 함.
        self.daily.mark()
        with mock.patch("learning_data.daily_study.request", return_value={"eligible": False, "date": self.day}) as request:
            self.daily.synchronize()
            self.daily.synchronize()
        self.assertEqual(1, request.call_count)
        self.assertFalse(self.daily.due())

    def test_old_server_error_keeps_the_signal_due(self):
        self.daily.mark()
        with mock.patch("learning_data.daily_study.request", side_effect=CollectionError("old server", status=404)):
            with self.assertRaises(CollectionError):
                self.daily.synchronize()
        self.assertTrue(self.daily.due())

    def test_account_switch_during_request_keeps_the_new_account_due(self):
        # 예전에는 요청 중에 선택을 끄면 삭제 대기가 남는지 봤음. 지금은 요청 중 바뀐 계정의 표식이 보존되는지 봄.
        self.daily.mark()
        def response(*args, **kwargs):
            self.identity.save({"verified": True, "team": False, "token": "b" * 64})
            DailyStudy(self.identity).mark()
            return self.sent()
        with mock.patch("learning_data.daily_study.request", side_effect=response) as request:
            self.daily.synchronize()
            self.assertEqual("a" * 64, request.call_args.kwargs["token"])
        self.assertTrue(self.daily.due())
        with mock.patch("learning_data.daily_study.request", return_value=self.sent()) as request:
            self.daily.synchronize()
            self.assertEqual("b" * 64, request.call_args.kwargs["token"])
        self.assertFalse(self.daily.due())

    def test_mark_waits_for_response_save_in_another_instance(self):
        # 예전에는 다른 인스턴스의 선택 끄기가 응답 저장을 기다리는지 봤음. 지금은 다른 계정의 표식이 덮이지 않는지 봄.
        self.daily.mark()
        saving, release = threading.Event(), threading.Event()
        marking, marked = threading.Event(), threading.Event()
        failures = []

        def delayed_save(path, value):
            if value.get("sent"):
                saving.set()
                if not release.wait(3):
                    raise AssertionError("응답 저장 대기를 끝내지 못함")
            save(path, value)

        def synchronize():
            try:
                self.daily.synchronize()
            except BaseException as error:
                failures.append(error)

        def mark_other():
            marking.set()
            try:
                with mock.patch.object(DailyStudy, "fingerprint", return_value="b" * 64):
                    DailyStudy(self.identity).mark()
            except BaseException as error:
                failures.append(error)
            finally:
                marked.set()

        worker, other = threading.Thread(target=synchronize), threading.Thread(target=mark_other)
        with mock.patch("learning_data.daily_study.save", side_effect=delayed_save), \
                mock.patch("learning_data.daily_study.request", return_value=self.sent()):
            worker.start()
            try:
                self.assertTrue(saving.wait(3))
                other.start()
                self.assertTrue(marking.wait(3))
                self.assertFalse(marked.wait(0.05))
            finally:
                release.set()
                worker.join(3)
                if other.ident is not None:
                    other.join(3)
        self.assertFalse(worker.is_alive())
        self.assertFalse(other.is_alive())
        self.assertEqual([], failures)
        state = json.loads(self.daily.path.read_text())
        self.assertEqual(2, len(state["graded"]))
        self.assertEqual(1, len(state["sent"]))
        self.assertFalse(self.daily.due())

    def test_network_wait_does_not_block_marking_in_another_instance(self):
        self.daily.mark()
        entered, done = threading.Event(), threading.Event()
        failures = []

        def response(*args, **kwargs):
            entered.set()
            if not done.wait(3):
                raise AssertionError("통신 대기가 채점 표식을 막음")
            return self.sent()

        def synchronize():
            try:
                self.daily.synchronize()
            except BaseException as error:
                failures.append(error)

        def mark_other():
            try:
                with mock.patch.object(DailyStudy, "fingerprint", return_value="b" * 64):
                    DailyStudy(self.identity).mark()
            except BaseException as error:
                failures.append(error)
            finally:
                done.set()

        worker, other = threading.Thread(target=synchronize), threading.Thread(target=mark_other)
        with mock.patch("learning_data.daily_study.request", side_effect=response):
            worker.start()
            try:
                self.assertTrue(entered.wait(3))
                other.start()
                self.assertTrue(done.wait(3))
            finally:
                done.set()
                worker.join(3)
                if other.ident is not None:
                    other.join(3)
        self.assertFalse(worker.is_alive())
        self.assertFalse(other.is_alive())
        self.assertEqual([], failures)
        self.assertEqual(2, len(json.loads(self.daily.path.read_text())["graded"]))

    def test_each_account_is_sent_separately_with_its_own_token(self):
        # 예전에는 계정을 바꿔도 이전 계정의 삭제 대기가 남는지 봤음. 지금은 계정마다 따로 한 번씩 보내는지 봄.
        self.daily.mark()
        with mock.patch("learning_data.daily_study.request", return_value=self.sent()) as request:
            self.daily.synchronize()
            self.identity.save({"verified": True, "team": False, "token": "b" * 64})
            self.daily.synchronize()
            self.assertEqual(1, request.call_count)
            self.assertTrue(self.daily.mark())
            self.daily.synchronize()
            self.identity.save({"verified": True, "team": False, "token": "a" * 64})
            self.assertFalse(self.daily.mark())
            self.daily.synchronize()
        self.assertEqual(["a" * 64, "b" * 64], [call.kwargs["token"] for call in request.call_args_list])
        saved = self.daily.path.read_text()
        for token in ("a" * 64, "b" * 64):
            self.assertNotIn(token, saved)

    def test_next_day_sends_again(self):
        # 예전에는 지난 날짜의 삭제 대기를 봤음. 지금은 날짜가 바뀌면 그날 채점으로 다시 보내는지 봄.
        self.daily.mark()
        tomorrow = datetime.datetime.now(KST) + datetime.timedelta(days=1)
        with mock.patch("learning_data.daily_study.request", return_value=self.sent()) as request:
            self.daily.synchronize()
            with mock.patch("learning_data.daily_study.datetime.datetime") as clock:
                clock.now.return_value = tomorrow
                next_day = tomorrow.date().isoformat()
                self.assertFalse(self.daily.due())
                self.daily.synchronize()
                self.assertEqual(1, request.call_count)
                self.assertTrue(self.daily.mark())
                request.return_value = {"eligible": True, "date": next_day}
                self.daily.synchronize()
        self.assertEqual([self.day, next_day], [call.args[2]["date"] for call in request.call_args_list])

    def test_previous_settings_file_is_replaced_without_sending_deletions(self):
        # 예전 선택 파일을 켰던 사람도 껐던 사람도 새 기준으로 셈. 삭제 대기 기록은 보내지 않고 지움.
        fingerprint = self.daily.fingerprint()
        for enabled in (True, False):
            with self.subTest(enabled=enabled):
                save(self.daily.path, {"version": "2026-11-16-v1", "enabled": enabled, "identity": fingerprint,
                                       "choice": "11111111-1111-4111-8111-111111111111", "at": "2026-11-16T10:00:00+09:00",
                                       "delete_pending": not enabled, "delete_date": self.day, "sent_date": self.day,
                                       "unresolved_deletions": [{"identity": fingerprint, "date": self.day}]})
                with mock.patch("learning_data.daily_study.request", return_value=self.sent()) as request:
                    self.assertFalse(self.daily.due())
                    self.daily.synchronize()
                    request.assert_not_called()
                    self.assertEqual({"version": VERSION, "date": self.day, "graded": [], "sent": []},
                                     json.loads(self.daily.path.read_text()))
                    self.assertTrue(self.daily.mark())
                    self.daily.synchronize()
                    request.assert_called_once()
                    self.assertEqual("POST", request.call_args.kwargs["method"])

    def test_broken_settings_file_does_not_stop_marking_or_sending(self):
        for broken in ("{", "[]", json.dumps({"version": VERSION, "date": self.day, "graded": "x", "sent": []})):
            with self.subTest(broken=broken):
                self.daily.path.write_text(broken, encoding="utf-8")
                self.assertFalse(self.daily.due())
                self.assertTrue(self.daily.mark())
                with mock.patch("learning_data.daily_study.request", return_value=self.sent()) as request:
                    self.daily.synchronize()
                    request.assert_called_once()

    def test_invalid_response_does_not_mark_sent(self):
        # 예전에는 잘못된 삭제 응답을 봤음. 지금은 날짜가 다른 응답을 전송 완료로 남기지 않는지 봄.
        self.daily.mark()
        with mock.patch("learning_data.daily_study.request", return_value={"eligible": True, "date": "2000-01-01"}):
            with self.assertRaises(CollectionError):
                self.daily.synchronize()
        self.assertTrue(self.daily.due())

    def test_alternate_server_cannot_receive_identity_or_study_signal(self):
        self.daily.mark()
        self.identity.base = "https://other.example"
        self.assertFalse(self.daily.due())
        with mock.patch("learning_data.daily_study.request") as request:
            self.daily.synchronize()
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
