# -*- coding: utf-8 -*-
"""Sobel 커널의 모든 곱을 더해 가운데 응답을 대조함."""


def a03_g01(params):
    """방향별 3×3 행렬을 입력에 직접 곱하고 마지막 코드 줄의 연산을 적용함."""
    kernels = {"x": ((-1, 0, 1), (-2, 0, 2), (-1, 0, 1)),
               "y": ((-1, -2, -1), (0, 0, 0), (1, 2, 1))}
    kernel = kernels[params["axis"]]
    response = sum(params["patch"][row][col] * kernel[row][col]
                   for row in range(3) for col in range(3))
    return [str(abs(response) if params["absolute"] else response)]
