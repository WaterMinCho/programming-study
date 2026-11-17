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


def i16_g06(p):
    side = int(p["side"])
    channels = int(p["channels"])
    form = p["form"]
    if side not in (24, 32, 40, 48, 56):
        raise ValueError("side must be one of 24, 32, 40, 48, 56")
    if channels <= 0:
        raise ValueError("channels must be positive")
    s = side
    for _ in range(3):
        s = s // 2
    feat = s * s * channels
    if form == "features":
        return [str(feat)]
    if form == "linear":
        hidden = int(p["hidden"])
        if hidden <= 0:
            raise ValueError("hidden must be positive")
        return [str(feat * hidden + hidden)]
    raise ValueError("form must be features or linear")



def i16_g07(params):
    """배치를 보존하고 잘못된 설정만 고치는 보기 문자열을 반환함."""
    for name in ("n", "c", "h", "w", "classes", "in_features"):
        if type(params[name]) is not int or params[name] <= 0:
            raise ValueError(f"{name}은 양의 정수여야 함.")
    start_dim = params["start_dim"]
    if type(start_dim) is not int or start_dim not in (0, 1):
        raise ValueError("공개 조건의 시작 축은 0 또는 1임.")
    per_image = params["c"] * params["h"] * params["w"]
    change_flat = start_dim != 1
    change_fc = params["in_features"] != per_image
    # 공개 보기 문자열의 조사와 마침표를 유지함.
    if change_flat and change_fc:
        choice = (f"flat의 start_dim을 1로, fc의 첫 인자를 "
                  f"{per_image}로 바꿉니다.")
    elif change_flat:
        choice = "flat의 start_dim만 1로 바꿉니다."
    elif change_fc:
        choice = f"fc의 첫 인자만 {per_image}로 바꿉니다."
    else:
        choice = "수정하지 않습니다."
    return [choice]
