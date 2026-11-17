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



def i03_g04(params):
    """선택한 축을 합산한 원소 목록과 남은 축의 크기를 반환함."""
    values = params["values"]
    dim = params["dim"]
    if type(dim) is not int or dim not in (0, 1):
        raise ValueError("공개 조건의 합산 축은 0 또는 1임.")
    if not isinstance(values, (list, tuple)) or not values:
        raise ValueError("한 행 이상인 배열이 필요함.")
    if not isinstance(values[0], (list, tuple)) or not values[0]:
        raise ValueError("한 열 이상인 배열이 필요함.")
    rows, columns = len(values), len(values[0])
    if any(not isinstance(row, (list, tuple)) or len(row) != columns
           for row in values):
        raise ValueError("모든 행의 길이가 같아야 함.")
    if any(type(value) is not int for row in values for value in row):
        raise ValueError("공개 조건의 원소는 정수임.")
    if dim == 0:
        reduced = [sum(values[r][c] for r in range(rows))
                   for c in range(columns)]
    else:
        reduced = [sum(row) for row in values]
    return [str(reduced), str([len(reduced)])]
