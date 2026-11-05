"""공개 입력 이름과 공개 지문의 계산 규칙으로 한 칸의 답을 반환함."""

from fractions import Fraction


def i10_g01(params):
    """입력에서 평균을 뺀 값을 표준편차로 나눔."""
    x = Fraction(str(params["x"]))
    mean = Fraction(str(params["mean"]))
    std = Fraction(str(params["std"]))
    return [str((x - mean) / std)]


def i10_g02(params):
    """남은 샘플을 포함해 배치 수를 계산함."""
    n = params["n"]
    size = params["size"]
    return [str((n + size - 1) // size)]


def i10_g03(params):
    """지운 원소는 0을 반환하고 남긴 원소에는 보정 배율을 곱함."""
    if not params["kept"]:
        return ["0"]
    value = Fraction(str(params["value"]))
    denominator = Fraction(str(params["denominator"]))
    probability = 1 / denominator
    return [str(value / (1 - probability))]


def i10_g04(params):
    """배치마다 평균 손실에 샘플 수를 곱해 합친 뒤 전체 수로 나눔."""
    a = params["a"]
    b = params["b"]
    loss_a = Fraction(str(params["loss_a"]))
    loss_b = Fraction(str(params["loss_b"]))
    return [str((a * loss_a + b * loss_b) / (a + b))]


def i10_g05(params):
    """전체 클래스를 포함한 단일 라벨 분류의 micro F1을 계산함."""
    return [str(Fraction(params["correct"], params["total"]))]
