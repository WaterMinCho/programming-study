"""공개 지문의 조건으로 계산한 답을 생성기의 입력 이름에 연결함."""
def g01_gap_flatten(shape):
    """NCHW 입력의 공간 평균과 배치 보존 펼치기를 계산함."""
    n, channels, height, width = shape
    return n, channels

def g02_replace_linear(total, in_features, old_out, new_out):
    """bias가 있는 마지막 Linear만 교체한 전체 파라미터를 계산함."""
    return total + (in_features + 1) * (new_out - old_out)

def g03_pool_flatten(channels, height, width, pool_count):
    """padding 0, ceil_mode False인 2×2 stride 2 풀링 뒤 특징 수를 계산함."""
    for _ in range(pool_count):
        height //= 2
        width //= 2
    if min(height, width) < 1:
        raise ValueError("풀링 뒤 공간 크기가 0임")
    return channels * height * width

def g04_topk_error(total, misses):
    """오차 백분율을 소수 첫째 자리로 표시함. 정확한 반올림 동률은 보류함."""
    if total <= 0 or not 0 <= misses <= total:
        raise ValueError("표본 수와 오답 수를 확인해야 함")
    tenths, remainder = divmod(misses * 1000, total)
    if 2 * remainder == total:
        raise ValueError("반올림 동률의 처리 규칙이 지문에 없음")
    if 2 * remainder > total:
        tenths += 1
    return f"{tenths // 10}.{tenths % 10}"


def i13_g01(p):
    return [str(g01_gap_flatten((p['n'],p['c'],p['h'],p['w'])))]


def i13_g02(p):
    return [str(g02_replace_linear(p['total'],p['f'],p['old'],p['new']))]


def i13_g03(p):
    return [str(g03_pool_flatten(p['channels'],p['side'],p['side'],p['count']))]


def i13_g04(p):
    return [str(g04_topk_error(p['total'],p['wrong']))]
