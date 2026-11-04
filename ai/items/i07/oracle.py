# -*- coding: utf-8 -*-
"""7차시 생성기의 정답을 생성기 코드를 쓰지 않고 독스트링의 식과 params 만으로 다시 계산함. 표준 라이브러리만 씀.

함수 이름은 생성기 id 의 붙임표를 밑줄로 바꾼 것이고, params 를 받아 칸마다 정답 글의 목록을 돌려줌. 계산은 Fraction 으로 함.
"""
from fractions import Fraction


def _text(value):
    """Fraction 을 소수 글로. 유한소수만 들어옴. 정수면 소수점을 붙이지 않음."""
    value = Fraction(value)
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


def i07_g01(params):
    """출력 j = Σ_i weight[j][i] × x[i] + bias[j]. 정답은 [[출력 0, 출력 1, …]] 꼴 한 칸."""
    outs = []
    for j in range(len(params["bias"])):
        total = Fraction(params["bias"][j])
        for i in range(len(params["x"])):
            total += Fraction(params["weight"][j][i]) * Fraction(params["x"][i])
        outs.append(_text(total))
    return ["[[" + ", ".join(outs) + "]]"]


def i07_g02(params):
    """weight 기울기 g = (2 ÷ n) × Σ(w × x + b − y) × x, half 면 g ÷ 2. ask 가 grad 면 g, step 이면 w − lr × g."""
    w, b = Fraction(params["w"]), Fraction(params["b"])
    xs = [Fraction(v) for v in params["x"]]
    ys = [Fraction(v) for v in params["y"]]
    n = len(xs)
    g = Fraction(0)
    for x, y in zip(xs, ys):
        g += (w * x + b - y) * x
    g = g * 2 / n
    if params["half"]:
        g = g / 2
    if params["ask"] == "grad":
        return [_text(g)]
    return [_text(w - Fraction(params["lr"]) * g)]


def i07_g03(params):
    """R² = 1 − Σ(y − 예측)² ÷ Σ(y − y 평균)²."""
    ys = [Fraction(v) for v in params["y"]]
    ps = [Fraction(v) for v in params["pred"]]
    mean = sum(ys) / len(ys)
    res = sum((y - p) ** 2 for y, p in zip(ys, ps))
    tot = sum((y - mean) ** 2 for y in ys)
    return [_text(1 - res / tot)]
