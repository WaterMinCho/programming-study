# -*- coding: utf-8 -*-
"""6차시 생성기의 정답을 생성기 코드를 쓰지 않고 독스트링의 식과 params 만으로 다시 계산함. 표준 라이브러리만 씀.

함수 이름은 생성기 id 의 붙임표를 밑줄로 바꾼 것이고, params 를 받아 칸마다 정답 글의 목록을 돌려줌. 계산은 Fraction 으로 함.
"""
from fractions import Fraction


def _text(value):
    """Fraction 을 소수 글로. 유한소수만 들어옴. 정수면 소수점을 붙이지 않음."""
    value = Fraction(value)
    if value.denominator == 1:
        return str(value.numerator)
    sign = "-" if value < 0 else ""
    value = abs(value)
    whole, rest = divmod(value.numerator, value.denominator)
    digits = ""
    while rest:
        rest *= 10
        digit, rest = divmod(rest, value.denominator)
        digits += str(digit)
        if len(digits) > 12:
            raise ValueError("유한소수가 아님")
    return "%s%d.%s" % (sign, whole, digits)


def i06_g01(params):
    """MSE 는 (예측 − 정답)² 의 평균, MAE 는 |예측 − 정답| 의 평균."""
    diffs = [Fraction(p) - Fraction(t) for p, t in zip(params["yp"], params["yt"])]
    if params["ask"] == "mse":
        return [_text(sum(d * d for d in diffs) / len(diffs))]
    return [_text(sum(abs(d) for d in diffs) / len(diffs))]


def i06_g02(params):
    """원소마다 |e| ≤ δ 이면 e² ÷ 2, 아니면 δ × |e| − δ² ÷ 2 를 구해 평균 냄."""
    d = Fraction(params["delta"])
    out = []
    for raw in params["errors"]:
        a = abs(Fraction(raw))
        out.append(a * a / 2 if a <= d else d * a - d * d / 2)
    return [_text(sum(out) / len(out))]


def i06_g03(params):
    """정답 칸은 (1 − α) + α ÷ K, 정답이 아닌 칸은 α ÷ K."""
    alpha, k = Fraction(params["alpha"]), Fraction(params["K"])
    spread = alpha / k
    return [_text(1 - alpha + spread if params["ask"] == "right" else spread)]


def i06_g04(params):
    """클래스 c 의 가중치 = 전체 데이터 수 ÷ (클래스 수 × n_c)."""
    counts = params["counts"]
    return [_text(Fraction(sum(counts), len(counts) * counts[params["cls"]]))]


def _positive_integer(value, name):
    """양의 정수 조건을 확인함."""
    if type(value) is not int or value <= 0:
        raise ValueError(f"{name}은 양의 정수여야 함.")
    return value


def _boolean(value, name):
    """불리언 조건을 확인함."""
    if type(value) is not bool:
        raise ValueError(f"{name}은 참 또는 거짓이어야 함.")
    return value


def _shape(value):
    """축 크기 목록을 비교 가능한 튜플로 바꿈."""
    if not isinstance(value, (list, tuple)) or not value:
        raise ValueError("배치 축을 포함하는 모양이 필요함.")
    return tuple(_positive_integer(size, "축 크기") for size in value)


def i06_g05(params):
    """모양과 입력 의미를 대조하고 새 보기 문구를 반환함."""
    batch = _positive_integer(params["batch"], "batch")
    output_shape = _shape(params["output_shape"])
    label_shape = _shape(params["label_shape"])
    if output_shape[0] != batch or label_shape[0] != batch:
        raise ValueError("배치 크기와 모양의 첫 축이 서로 맞지 않음.")
    has_probability = _boolean(params["apply_sigmoid"], "apply_sigmoid")
    loss_name = params["loss_name"]
    if loss_name not in ("BCELoss", "BCEWithLogitsLoss"):
        raise ValueError("공개 조건에 없는 손실 함수임.")
    shape_matches = output_shape == label_shape
    kind_matches = has_probability == (loss_name == "BCELoss")
    if shape_matches and kind_matches:
        answer = "모양이 같고 손실에 맞는 값을 넣었습니다."
    elif shape_matches:
        answer = "모양은 같지만 logit과 확률 중 잘못된 쪽을 넣었습니다."
    elif kind_matches:
        answer = "손실에 넣은 값은 맞지만 출력과 정답의 모양을 맞춰야 합니다."
    else:
        answer = "모양과 logit·확률 구분을 모두 고쳐야 합니다."
    return [answer]
