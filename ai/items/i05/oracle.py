# -*- coding: utf-8 -*-
"""5차시 생성기의 정답을 독스트링과 params 만으로 다시 계산함. 표준 라이브러리만 씀.

함수 이름은 생성기 id 의 붙임표를 밑줄로 바꾼 것이고, params 를 받아 칸마다 정답 글의 목록을 돌려줌.
"""
from decimal import Decimal, ROUND_HALF_UP


def _text(value):
    """Decimal 을 지수 표기 없는 글로. 정수면 소수점을 붙이지 않음."""
    value = Decimal(value).normalize()
    if value == value.to_integral_value():
        return str(int(value))
    return format(value, "f")


def i05_g01(params):
    """층마다 입력 수 × 출력 수 + 출력 수를 더한 파라미터 수."""
    s = params["sizes"]
    total = 0
    for k in range(len(s) - 1):
        total += s[k] * s[k + 1] + s[k + 1]
    return [str(total)]


def i05_g02(params):
    """r 을 n 번 곱한 값을 소수 넷째 자리까지 반올림."""
    value = Decimal(params["r"]) ** int(params["n"])
    return [str(value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))]


def i05_g03(params):
    """배치 수는 N 을 B 로 나눈 몫을 올림, 마지막 배치는 나머지(0 이면 B), 전체는 배치 수 × 에폭."""
    n, b = int(params["N"]), int(params["B"])
    count = n // b + (1 if n % b else 0)
    if params["ask"] == "count":
        return [str(count)]
    if params["ask"] == "last":
        return [str(n % b or b)]
    return [str(count * int(params["E"]))]


def i05_g04(params):
    """평균, 데이터 수로 나눈 분산, x̂ = (값 − 평균) ÷ √분산, y = γx̂ + β."""
    values = [Decimal(v) for v in params["values"]]
    mean = sum(values) / len(values)
    var = sum((v - mean) * (v - mean) for v in values) / len(values)
    if params["ask"] == "var":
        return [_text(var)]
    xhat = (Decimal(params["pick"]) - mean) / var.sqrt()
    if params["ask"] == "xhat":
        return [_text(xhat)]
    return [_text(Decimal(params["gamma"]) * xhat + Decimal(params["beta"]))]


def i05_g05(params):
    """0 부터 E − 1 까지 k 의 배수에서 기록. 마지막 배수나 기록 개수."""
    e, k = int(params["E"]), int(params["k"])
    marks = [epoch for epoch in range(e) if epoch % k == 0]
    return [str(marks[-1])] if params["ask"] == "last" else [str(len(marks))]
