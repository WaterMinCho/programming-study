"""공개한 조건으로 끝에 붙는 0의 개수나 남는 낱말 수, 디코더 층의 파라미터 수, METEOR 값을 생성기와 따로 계산함."""
from decimal import Decimal, ROUND_HALF_UP
from fractions import Fraction


def a08_g01(params):
    ids = [1]
    for _ in range(params["words"]):
        ids.append(4)
        if len(ids) >= params["max_len"] - 1:
            break
    ids.append(2)
    ids += [0] * (params["max_len"] - len(ids))
    if params["form"] == "zeros":
        return [str(ids.count(0))]
    return [str(ids.count(4))]


def a08_g02(params):
    v, e, h = params["V"], params["E"], params["H"]
    table = {
        "embedding": v * e,
        "lstm": 4 * h * e + 4 * h * h + 8 * h,
        "linear": (h + 1) * v,
    }
    table["total"] = table["embedding"] + table["lstm"] + table["linear"]
    return [str(table[params["form"]])]


def _round4(q):
    value = Decimal(q.numerator) / Decimal(q.denominator)
    return str(value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))


def a08_g03(params):
    m, c, r, k = params["m"], params["cand_len"], params["ref_len"], params["k"]
    p, rec = Fraction(m, c), Fraction(m, r)
    fmean = 10 * p * rec / (rec + 9 * p)
    pen = Fraction(1, 2) * Fraction(k, m) ** 3
    value = {"fmean": fmean, "penalty": pen, "score": fmean * (1 - pen)}[params["form"]]
    return [_round4(value)]
