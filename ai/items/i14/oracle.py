"""공개 지문의 조건으로 계산한 답을 생성기의 입력 이름에 연결함."""
from decimal import Decimal

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
