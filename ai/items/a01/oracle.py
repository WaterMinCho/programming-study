# -*- coding: utf-8 -*-
"""배열 원소를 비트 단위로 더해 두 저장 방식의 결과를 대조함."""


def a01_g01(params):
    """8비트 덧셈의 자리올림을 추적하고 넘친 경우에만 포화값을 씀."""
    saturated, wrapped = [], []
    for left, right in zip(params["a"], params["b"]):
        carry, value = 0, 0
        for bit in range(8):
            digits = ((left >> bit) & 1) + ((right >> bit) & 1) + carry
            value |= (digits & 1) << bit
            carry = digits >> 1
        saturated.append(255 if carry else value)
        wrapped.append(value)
    return [str(saturated), str(wrapped)]
