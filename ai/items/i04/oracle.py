# -*- coding: utf-8 -*-
"""4차시 생성기의 정답을 생성기 코드를 보지 않고 공개본의 독스트링과 params 만으로 다시 계산함. 표준 라이브러리만 씀.

함수 이름은 생성기 id 의 붙임표를 밑줄로 바꾼 것이고, params 를 받아 칸마다 정답 글의 목록을 돌려줌.
"""
from decimal import Decimal


def _text(value):
    """Decimal 을 지수 표기 없는 글로 바꿈. 정수면 소수점을 붙이지 않음."""
    value = value.normalize()
    if value == value.to_integral_value():
        return str(int(value))
    return format(value, "f")


def i04_g01(params):
    """예측과 정답의 평균 제곱 오차."""
    yp = [Decimal(v) for v in params["Yp"]]
    y = [Decimal(v) for v in params["Y"]]
    return [_text(sum((a - b) ** 2 for a, b in zip(yp, y)) / len(y))]


def i04_g02(params):
    """경사하강법 한 걸음. ask 가 new 면 새 W, grad 면 (W − 새 W) ÷ 학습률."""
    w, lr = Decimal(params["W"]), Decimal(params["lr"])
    if params["ask"] == "new":
        return [_text(w - lr * Decimal(params["gW"]))]
    return [_text((w - Decimal(params["new"])) / lr)]


def i04_g03(params):
    """한 데이터가 W.grad 에 보태는 값 (1/n) × 2e × 1 × X."""
    n, e, x = Decimal(params["n"]), Decimal(params["e"]), Decimal(params["X"])
    return [_text(2 * e * x / n)]
