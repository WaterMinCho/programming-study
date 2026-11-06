# -*- coding: utf-8 -*-
"""공개 지문에서 별도로 계산한 창 수를 연결함."""


def feature_count(side: int, channels: int, batch: int) -> int:
    """배치 축을 제외한 한 이미지의 원소 수를 반환함.

    매개변수는 bool을 제외한 int만 받음. side는 4 이상이며 나머지는 양수임.
    batch는 입력 조건을 검사할 때 사용하며 반환값에 곱하지 않음.
    이 함수는 공개 지문의 고정 연산만 계산하며 일반 CNN을 해석하지 않음.
    """
    for name, value in (("side", side), ("channels", channels), ("batch", batch)):
        if not isinstance(value, int) or isinstance(value, bool):
            raise TypeError(name + " must be an integer")
        if value < 1:
            raise ValueError(name + " must be positive")
    if side < 4:
        raise ValueError("side must allow two complete pooling windows")

    spatial = side
    for _ in range(2):
        # 합성곱은 양쪽 패딩으로 공간을 유지함. 풀링에서 남는 한 칸은 세지 않음.
        spatial = len(range(0, spatial - 1, 2))
    return channels * spatial * spatial


def pc_g01(p):
    return [str(feature_count(p["side"], p["channels"], p["batch"]))]
