# -*- coding: utf-8 -*-
"""정방향 행렬 계산과 원본 후보 탐색으로 좌표를 대조함."""


def a02_g01(params):
    """정방향 관계로 두 좌표를 독립 대조함.

    point는 direction이 source_to_destination이면 원본 점,
    destination_to_source이면 출력 점으로 읽음.
    """
    allowed = {"point", "translation", "direction"}
    if not isinstance(params, dict) or set(params) != allowed:
        raise ValueError("params 키는 point, translation, direction 셋이어야 함")

    def int_pair(name):
        value = params[name]
        if not isinstance(value, (list, tuple)) or len(value) != 2:
            raise ValueError(f"{name}은 정수 두 개여야 함")
        for n in value:
            # bool은 int의 하위 타입이어서 따로 거름
            if isinstance(n, bool) or not isinstance(n, int):
                raise ValueError(f"{name}은 정수 두 개여야 함")
        return value[0], value[1]

    px, py = int_pair("point")
    tx, ty = int_pair("translation")
    matrix = ((1, 0, tx), (0, 1, ty))

    def forward(x, y):
        # 2×3 행렬의 각 행을 [x, y, 1]에 곱해 더함
        vec = (x, y, 1)
        return tuple(sum(m * v for m, v in zip(row, vec)) for row in matrix)

    direction = params["direction"]
    if direction == "source_to_destination":
        answer = forward(px, py)
    elif direction == "destination_to_source":
        span_x, span_y = abs(tx) + 1, abs(ty) + 1
        if (2 * span_x + 1) * (2 * span_y + 1) > 121:
            raise ValueError("이동이 커서 탐색 범위를 넘음")
        # 원본 점 후보를 정방향 식에 넣어 출력 점과 맞는 것만 남김
        found = [
            (x, y)
            for x in range(px - span_x, px + span_x + 1)
            for y in range(py - span_y, py + span_y + 1)
            if forward(x, y) == (px, py)
        ]
        if len(found) != 1:
            raise ValueError("정방향 관계를 만족하는 원본 점이 하나가 아님")
        answer = found[0]
    else:
        raise ValueError("direction 값을 알 수 없음")

    return [str(answer[0]), str(answer[1])]
