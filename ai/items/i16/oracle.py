"""공개 지문의 조건으로 계산한 답을 생성기의 입력 이름에 연결함."""
from fractions import Fraction

def g01_window_sum(window, kernel):
    """필터를 뒤집지 않은 2×2 창의 곱 합을 bias 0으로 계산함."""
    if len(window) != 2 or len(kernel) != 2 or any(len(row) != 2 for row in window + kernel):
        raise ValueError("2×2 창과 필터가 필요함")
    return sum(window[r][c] * kernel[r][c] for r in range(2) for c in range(2))

def g02_output_side(height, kernel_size, padding, stride):
    """dilation 1인 공개 출력 길이 식을 정수 나눗셈으로 계산함."""
    return (height + 2 * padding - kernel_size) // stride + 1

def g03_pool_value(values, kind):
    """패딩 없는 2×2 창에서 요청한 최댓값 또는 평균을 계산함."""
    if len(values) != 4:
        raise ValueError("창 원소가 네 개여야 함")
    if kind == "max":
        return max(values)
    if kind == "avg":
        return Fraction(sum(values), 4)
    raise ValueError("kind를 max 또는 avg로 지정해야 함")

def g04_flatten_length(side, channels, pool_count):
    """공간 유지 합성곱과 2×2 stride 2 풀링 뒤 샘플당 특징 수를 계산함."""
    for _ in range(pool_count):
        side //= 2
    if side < 1:
        raise ValueError("풀링 뒤 공간 크기가 0임")
    return channels * side * side

def g05_conv_parameters(in_channels, out_channels, kernel_size, bias):
    """groups 1인 정사각 커널 Conv2d의 weight와 선택한 bias 수를 계산함."""
    if type(bias) is not bool:
        raise ValueError("bias 여부를 명시해야 함")
    return in_channels * out_channels * kernel_size ** 2 + (out_channels if bias else 0)


def i16_g01(p):
    return [str(g01_window_sum([p['x'][:2],p['x'][2:]],[p['k'][:2],p['k'][2:]]))]


def i16_g02(p):
    return [str(g02_output_side(p['h'],p['k'],p['p'],p['s']))]


def i16_g03(p):
    return [str(g03_pool_value(p['x'],'avg' if p['form']=='mean' else 'max'))]


def i16_g04(p):
    return [str(g04_flatten_length(p['side'],p['c'],p['count']))]


def i16_g05(p):
    return [str(g05_conv_parameters(p['ci'],p['co'],p['k'],p['bias']))]
