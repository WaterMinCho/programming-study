"""공개 지문의 조건으로 계산한 답을 생성기의 입력 이름에 연결함."""
from decimal import Decimal
from fractions import Fraction

def g01_group_sgd(value, gradient, default_lr, group_factor):
    """모멘텀과 weight decay 없는 그룹 SGD의 한 갱신을 계산함."""
    return Decimal(str(value)) - Decimal(str(default_lr)) * Decimal(str(group_factor)) * Decimal(str(gradient))

def g02_lambda_lr(initial_lr, index, threshold, later_factor):
    """인덱스 경계 전에는 1, 이후에는 주어진 배수를 초기 lr에 곱함."""
    factor = Decimal(1) if index < threshold else Decimal(str(later_factor))
    return Decimal(str(initial_lr)) * factor

def g03_unfreeze_count(epoch, interval):
    """14e의 공개 0_step에 명시한 1부터 세는 에폭 공식을 사용함."""
    if epoch < 1 or interval < 1:
        raise ValueError("에폭과 구간 길이는 양수여야 함")
    return min(4, (epoch - 1) // interval)

def g04_projection_weights(in_channels, out_channels):
    """groups 1, bias False인 1×1 투영 합성곱의 weight 수를 계산함."""
    return in_channels * out_channels


def i14_g01(p):
    return [str(g01_group_sgd(p['initial'],p['grad'],p['base'],p['factor']))]


def i14_g02(p):
    return [str(g02_lambda_lr(p['base'],p['index'],p['boundary'],p['factor']))]


def i14_g03(p):
    return [str(g03_unfreeze_count(p['epoch'],p['k']))]


def i14_g04(p):
    return [str(g04_projection_weights(p['ci'],p['co']))]


def _boolean(value, name):
    """불리언 조건을 확인함."""
    if type(value) is not bool:
        raise ValueError(f"{name}은 참 또는 거짓이어야 함.")
    return value


def _number_text(value):
    """유한소수를 나눗셈으로 끝까지 계산하여 문자열로 반환함."""
    value = Fraction(value)
    denominator = value.denominator
    residue = denominator
    for factor in (2, 5):
        while residue % factor == 0:
            residue //= factor
    if residue != 1:
        raise ValueError("유한소수로 표시할 수 없는 값임.")
    integer, remainder = divmod(abs(value.numerator), denominator)
    digits = []
    while remainder:
        digit, remainder = divmod(remainder * 10, denominator)
        digits.append(str(digit))
    text = str(integer) + (("." + "".join(digits)) if digits else "")
    return ("-" if value < 0 else "") + text


def i14_g05(params):
    """등록 여부와 남은 grad로 SGD 갱신 뒤 값을 계산함."""
    initial = Fraction(str(params["initial"]))
    learning_rate = Fraction(str(params["lr"]))
    if learning_rate < 0:
        raise ValueError("학습률은 음수가 될 수 없음.")
    registered = _boolean(params["registered"], "registered")
    _boolean(params["requires_grad"], "requires_grad")
    stored_grad = params["stored_grad"]
    if stored_grad is not None:
        stored_grad = Fraction(str(stored_grad))
    # requires_grad의 변경은 이미 남은 grad를 지우지 않음.
    updated = initial
    if registered and stored_grad is not None:
        updated -= learning_rate * stored_grad
    return [_number_text(updated)]
