"""apc-g101 의 묶음 수를 나눗셈과 나머지로 따로 계산함."""


def apc_g101(p):
    count, rest = divmod(p["n"], p["size"])
    return [str(count + bool(rest))]
