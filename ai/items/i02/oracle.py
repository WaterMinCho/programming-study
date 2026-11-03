# -*- coding: utf-8 -*-
"""2차시 생성기 대조용 정답 계산. 생성기 코드를 보지 않고 공개본의 독스트링과 params 로만 다시 씀."""


def _shape(dims):
    return "(" + ", ".join(str(d) for d in dims) + ("," if len(dims) == 1 else "") + ")"


def _vec(values):
    return "[" + ", ".join(str(x) for x in values) + "]"


def i02_g01(params):
    """-1 자리는 전체 원소 수를 나머지 길이의 곱으로 나눈 몫임."""
    total, asked = params["total"], list(params["asked"])
    known = 1
    for d in asked:
        if d != -1:
            known *= d
    return [_shape([total // known if d == -1 else d for d in asked])]


def i02_g02(params):
    """axis=0 은 열마다 위아래로, axis=1 은 행마다 옆으로 더함."""
    mat, axis = params["mat"], params["axis"]
    if axis == 0:
        sums = [sum(row[j] for row in mat) for j in range(len(mat[0]))]
    else:
        sums = [sum(row) for row in mat]
    return [_vec(sums)]


def i02_g03(params):
    """뒤 축부터 맞춰 길이가 같거나 한쪽이 1 이면 늘리고, 아니면 ValueError 임."""
    left, right = list(params["left"]), list(params["right"])
    n = max(len(left), len(right))
    left = [1] * (n - len(left)) + left
    right = [1] * (n - len(right)) + right
    out = []
    for a, b in zip(left, right):
        if a == b or b == 1:
            out.append(a)
        elif a == 1:
            out.append(b)
        else:
            return "ValueError가 납니다."
    return "shape %s 인 배열이 됩니다." % _shape(out)


def i02_g04(params):
    """조건이 참인 원소만 원래 순서대로 남김."""
    values, op, t = params["values"], params["op"], params["t"]
    keep = [x for x in values if (x > t if op == ">" else x >= t)]
    return [_vec(keep)]


def i02_g05(params):
    """axes 가 없으면 축 순서를 뒤집고, 있으면 새 축 i 의 길이가 원래 축 axes[i] 의 길이임."""
    shape, axes = list(params["shape"]), params["axes"]
    if axes is None:
        return [_shape(shape[::-1])]
    return [_shape([shape[i] for i in axes])]
