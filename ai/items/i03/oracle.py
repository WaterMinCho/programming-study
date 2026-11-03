# -*- coding: utf-8 -*-
"""3차시 생성기의 정답. 생성기 코드를 보지 않고 공개본의 독스트링과 params 만으로 다시 씀."""


def _squeeze(shape, dim):
    if dim is None:
        return [n for n in shape if n != 1]
    d = dim + len(shape) if dim < 0 else dim
    if shape[d] != 1:
        return list(shape)
    return shape[:d] + shape[d + 1:]


def _unsqueeze(shape, dim):
    d = dim + len(shape) + 1 if dim < 0 else dim
    return shape[:d] + [1] + shape[d:]


def i03_g01(params):
    shape = list(params["start"])
    for op, dim in params["ops"]:
        shape = _squeeze(shape, dim) if op == "squeeze" else _unsqueeze(shape, dim)
    return ["[" + ", ".join(str(n) for n in shape) + "]"]


def i03_g02(params):
    a, b = params["a"], params["b"]
    c = [[sum(a[i][k] * b[k][j] for k in range(2)) for j in range(2)] for i in range(2)]
    return ["[[%d, %d], [%d, %d]]" % (c[0][0], c[0][1], c[1][0], c[1][1])]


def i03_g03(params):
    grad = 2 * params["a"] * params["x0"] * (2 if params["twice"] else 1)
    return [str(grad)]
