# -*- coding: utf-8 -*-
"""시험 차시 생성기의 정답(생성기 코드를 보지 않고 쓴 판)."""
from decimal import Decimal


def i90_g01(params):
    new = Decimal(params["w"]) - Decimal(params["lr"]) * Decimal(params["g"])
    return [format(new.normalize(), "f")]


def i90_g02(params):
    n, b = params["n"], params["b"]
    return str((n + b - 1) // b)
