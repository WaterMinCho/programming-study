# -*- coding: utf-8 -*-
"""1차시 생성기의 정답을 생성기 코드를 보지 않고 공개본의 독스트링과 params 만으로 다시 계산함. 표준 라이브러리만 씀.

함수 이름은 생성기 id 의 붙임표를 밑줄로 바꾼 것이고, params 를 받아 칸마다 정답 글의 목록을 돌려줌.
"""
from decimal import Decimal


def _text(value):
    """Decimal 을 지수 표기 없이 쓰고 끝의 0 과 소수점을 뗌."""
    out = format(value.normalize(), "f")
    if "." in out:
        out = out.rstrip("0").rstrip(".")
    return "0" if out in ("-0", "") else out


def _listing(values):
    return "[" + ", ".join(str(x) for x in values) + "]"


def i01_g01(params):
    """Param − lr × grad 한 번."""
    p, lr, g = Decimal(str(params["p"])), Decimal(str(params["lr"])), Decimal(str(params["g"]))
    return [_text(p - lr * g)]


def i01_g02(params):
    """b = a 면 a 를 고친 값이 b 에 보이고, b = a.copy() 면 처음 값 그대로임."""
    before = list(params["a"])
    if params["copied"]:
        return [_listing(before)]
    after = list(before)
    after[params["i"]] = params["v"]
    return [_listing(after)]


def i01_g03(params):
    """order 의 세 함수를 f1, f2, f3 순서로 x 에 차례로 적용함."""
    k, c = params["k"], params["c"]
    step = {"square": lambda v: v * v, "mul": lambda v: v * k, "add": lambda v: v + c}
    value = params["x"]
    for name in params["order"]:
        value = step[name](value)
    return [str(value)]


def _bound(text):
    text = text.strip()
    return int(text) if text else None


def i01_g04(params):
    """code 의 대괄호 안 슬라이스를 직접 풀어 data 에 적용함."""
    code = params["code"].strip()
    inside = code[code.index("[") + 1:code.rindex("]")]
    parts = inside.split(":")
    start, stop = _bound(parts[0]), _bound(parts[1])
    step = _bound(parts[2]) if len(parts) > 2 else None
    return [_listing(list(params["data"])[slice(start, stop, step)])]
