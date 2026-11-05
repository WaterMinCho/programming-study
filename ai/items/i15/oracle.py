"""공개 지문의 조건으로 계산한 답을 생성기의 입력 이름에 연결함."""
from decimal import Decimal

def g01_resize_width(width, height, short_side):
    """max_size 없는 Resize의 공개 정수 비율 표본에서 출력 가로를 계산함."""
    if min(width, height, short_side) <= 0:
        raise ValueError("양의 이미지 크기가 필요함")
    result, remainder = divmod(width * short_side, min(width, height))
    if remainder:
        raise NotImplementedError("비정수 출력 길이의 정수화 규칙 확인이 필요함")
    return result

def g02_normalized_pixel(pixel):
    """uint8의 255 나누기와 0.5 상수 정규화를 소수 셋째 자리로 계산함."""
    if type(pixel) is not int or not 0 <= pixel <= 255:
        raise ValueError("uint8 정수 픽셀이 필요함")
    value = Decimal(2 * pixel) / Decimal(255) - Decimal(1)
    return format(value, ".3f")

def g03_batching(total, batch_size, query):
    """drop_last False에서 요청한 배치 수 또는 마지막 배치 크기를 계산함."""
    if total < 1 or batch_size < 1:
        raise ValueError("양의 표본 수와 배치 크기가 필요함")
    if query == "count":
        return (total + batch_size - 1) // batch_size
    if query == "last":
        return (total - 1) % batch_size + 1
    raise ValueError("query를 count 또는 last로 명시해야 함")


def i15_g01(p):
    return [str(g01_resize_width(p['long'],p['short'],p['target']))]


def i15_g02(p):
    return [str(g02_normalized_pixel(p['pixel']))]


def i15_g03(p):
    return [str(g03_batching(p['n'],p['size'],p['form']))]
