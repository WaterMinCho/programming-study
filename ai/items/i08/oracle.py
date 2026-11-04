# -*- coding: utf-8 -*-
"""8차시 생성기의 정답을 생성기 코드와 따로 계산함. 함수마다 params 를 받아 칸마다 정답 글의 목록을 돌려줌."""
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction


def _plain(value):
    text = format(Decimal(value.numerator) / Decimal(value.denominator), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _round(value, places):
    exact = Decimal(value.numerator) / Decimal(value.denominator)
    return str(exact.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP))


def i08_g01(params):
    probs = [Decimal(p) for p in params["p"]]
    half = Decimal("0.5")
    if params["rule"] == "gt":
        pred = [1 if p > half else 0 for p in probs]
    elif params["rule"] in ("ge", "where"):
        pred = [0 if p < half else 1 for p in probs]
    else:
        raise ValueError(params["rule"])
    same = sum(int(a == b) for a, b in zip(pred, params["y"]))
    return [_plain(Fraction(same, len(probs)))]


def i08_g02(params):
    (tn, fp), (fn, tp) = params["cm"]
    value = {"acc": Fraction(tp + tn, tn + fp + fn + tp), "prec": Fraction(tp, tp + fp), "rec": Fraction(tp, tp + fn),
             "f1": 2 * Fraction(tp, tp + fp) * Fraction(tp, tp + fn) / (Fraction(tp, tp + fp) + Fraction(tp, tp + fn))}
    return [_round(value[params["metric"]], 3)]


def i08_g03(params):
    neg, pos = params["neg"], params["pos"]
    if params["ask"] == "weight":
        return [_plain(Fraction(neg, pos))]
    return [_round(Fraction(neg, neg + pos), 3)]


def i08_g04(params):
    w1, w2, b, x1 = params["w1"], params["w2"], params["b"], params["x1"]
    return [_plain(Fraction(-b - w1 * x1, w2))]
