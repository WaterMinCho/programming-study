# -*- coding: utf-8 -*-
"""9차시 생성기의 정답을 생성기 코드를 쓰지 않고 독스트링의 식과 params 만으로 다시 계산함. 표준 라이브러리만 씀.

함수 이름은 생성기 id 의 붙임표를 밑줄로 바꾼 것이고, params 를 받아 칸마다 정답 글의 목록을 돌려줌. 반올림은 ROUND_HALF_UP 임.
"""
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction

E_POW = (Decimal("1"), Decimal("2.718"), Decimal("7.389"), Decimal("20.086"))


def _round(value, places):
    return str(Decimal(value).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP))


def _frac(value, places):
    value = Fraction(value)
    return _round(Decimal(value.numerator) / Decimal(value.denominator), places)


def _plain(value):
    """Fraction 이나 Decimal 을 끝의 0 없는 소수 글로(유한소수만 들어옴)."""
    value = Fraction(str(value)) if isinstance(value, Decimal) else Fraction(value)
    if value.denominator == 1:
        return str(value.numerator)
    sign = "-" if value < 0 else ""
    value = abs(value)
    whole, rest = divmod(value.numerator, value.denominator)
    digits = ""
    while rest:
        rest *= 10
        digit, rest = divmod(rest, value.denominator)
        digits += str(digit)
        if len(digits) > 12:
            raise ValueError("유한소수가 아님")
    return "%s%d.%s" % (sign, whole, digits)


def i09_g01(params):
    """weight 모양은 [C, F], 학습 파라미터는 F × C + C."""
    f, c = params["F"], params["C"]
    if params["form"] == "shape":
        return ["[%d, %d]" % (c, f)]
    return [str(f * c + c)]


def i09_g02(params):
    """클래스 k 의 확률 = e^(z_k) ÷ Σ e^(z). 더한 수 c 는 확률을 바꾸지 않으므로 더하기 전 logit z 의 어림한 e 값으로 셈."""
    powers = [E_POW[v] for v in params["z"]]
    return [_round(powers[params["k"]] / sum(powers), 3)]


def i09_g03(params):
    """정답 칸 로그 확률의 부호를 바꿔 reduction 이 'sum' 이면 더하고 'mean' 이면 평균."""
    picks = [-Fraction(row[y]) for row, y in zip(params["logp"], params["y"])]
    total = sum(picks)
    return [_plain(total if params["reduction"] == "sum" else total / len(picks))]


def i09_g04(params):
    """정확도 = 대각선 합 ÷ 전체, 정밀도 = m[k][k] ÷ k 열 합, 재현율 = m[k][k] ÷ k 행 합, F1 = 2·m[k][k] ÷ (열 합 + 행 합)."""
    m, k = params["m"], params["k"]
    col = sum(line[k] for line in m)
    row = sum(m[k])
    if params["metric"] == "acc":
        value = Fraction(sum(m[i][i] for i in range(len(m))), sum(sum(line) for line in m))
    elif params["metric"] == "prec":
        value = Fraction(m[k][k], col)
    elif params["metric"] == "rec":
        value = Fraction(m[k][k], row)
    else:
        value = Fraction(2 * m[k][k], col + row)
    return [_frac(value, 3)]


def i09_g05(params):
    """행마다 가장 큰 값의 위치가 예측. form 이 pred 면 그 목록, acc 면 정답과 같은 자리의 비율."""
    pred = []
    for row in params["rows"]:
        values = [Fraction(v) for v in row]
        pred.append(values.index(max(values)))
    if params["form"] == "pred":
        return ["[%s]" % ", ".join(str(p) for p in pred)]
    hits = sum(1 for p, y in zip(pred, params["y"]) if p == y)
    return [_plain(Fraction(hits, len(pred)))]
