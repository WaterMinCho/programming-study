# -*- coding: utf-8 -*-
"""장애 때의 전송 분산·상한과 빠른 철회 재시도를 확인함."""
import random
import unittest
from unittest import mock

from aiprep import sync_schedule


class SyncScheduleTest(unittest.TestCase):
    def test_delay_spreads_success_and_increases_failed_retries_with_a_cap(self):
        for failures, low, high in ((0, 48, 72), (1, 96, 144), (2, 192, 288), (4, 720, 900), (10, 720, 900)):
            with self.subTest(failures=failures):
                with mock.patch.object(sync_schedule.secrets, "randbelow", return_value=0):
                    self.assertEqual(low * 1000, sync_schedule.delay_ms(failures))
                with mock.patch.object(sync_schedule.secrets, "randbelow", side_effect=lambda n: n - 1):
                    self.assertEqual(high * 1000, sync_schedule.delay_ms(failures))

    def test_withdrawal_is_not_delayed_by_the_failed_upload_backoff(self):
        with mock.patch.object(sync_schedule.secrets, "randbelow", return_value=0):
            self.assertEqual(48000, sync_schedule.delay_ms(4, withdrawing=True))

    def test_startup_jitter_leaves_question_selection_random_state_unchanged(self):
        before = random.getstate()
        self.assertTrue(0 <= sync_schedule.initial_ms() <= 15000)
        self.assertEqual(before, random.getstate())
