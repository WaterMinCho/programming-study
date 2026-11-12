# -*- coding: utf-8 -*-
"""문제 선택 난수에 영향을 주지 않고 자동 전송 시점을 분산함."""
import secrets


def delay_ms(failures=0, withdrawing=False):
    base = 60 if withdrawing else min(900, 60 * 2 ** min(failures, 4))
    low, high = int(base * 0.8), min(900, int(base * 1.2))
    return (low + secrets.randbelow(high - low + 1)) * 1000


def initial_ms():
    return secrets.randbelow(15001)
