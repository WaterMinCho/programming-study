# -*- coding: utf-8 -*-
"""Sobel의 입력 영역·미분 방향·부호 처리 조건을 바꾸는 문항군임."""
from aiprep.gen import blank, gen


@gen("a03-g01", unit="a3b", level=3, tags=["app.a3b"],
     ref=["응용 3차시 슬 p7",
          "OpenCV 문서 Sobel"],
     facts=["FA03-b2"], basis="lecture-formula", step="a3b/3",
     family="a03-b07", core=False, prio=1)
def sobel_response(r):
    """작은 영역의 방향별 차이에 평활화 가중치를 곱해 가운데 응답을 구함."""
    patch = [[5 * r.int(0, 12) for _ in range(3)] for _ in range(3)]
    axis = r.pick(("x", "y"))
    absolute = r.chance(0.5)
    if axis == "x":
        parts = [row[2] - row[0] for row in patch]
        kernel = [[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]]
        dx, dy = 1, 0
    else:
        parts = [patch[2][col] - patch[0][col] for col in range(3)]
        kernel = [[-1, -2, -1], [0, 0, 0], [1, 2, 1]]
        dx, dy = 0, 1
    response = parts[0] + 2 * parts[1] + parts[2]
    value = abs(response) if absolute else response
    last = "value = int(abs(response[1, 1]))" if absolute else "value = int(response[1, 1])"
    code = ("import cv2\nimport numpy as np\n\n"
            f"patch = np.array({patch}, dtype=np.uint8)\n"
            f"response = cv2.Sobel(patch, cv2.CV_64F, {dx}, {dy}, ksize=3)\n{last}")
    stem = (f"{axis}방향 밝기 변화를 계산합니다. 사용하는 3×3 커널은 {kernel}입니다. "
             "영역과 커널의 같은 위치끼리 곱한 값을 모두 더합니다. "
             "가운데 위치만 물으므로 영역 바깥의 경계 처리는 계산하지 않습니다.\n\n"
             f"```python\n{code}\n```\n\n"
             "마지막 줄을 실행한 뒤 value는 ____ 입니다.")
    explain = (f"{axis}방향 차이는 {parts}입니다. "
               f"가중치 1, 2, 1을 적용한 합은 {parts[0]} + 2 × ({parts[1]}) + ({parts[2]}) = {response}입니다. "
               "CV_64F 응답은 음수도 보존합니다. ")
    explain += (f"마지막 줄에서 절댓값을 취해 value는 {value}입니다." if absolute
                else f"마지막 줄은 부호를 유지해 value는 {value}입니다.")
    return blank(stem, [{"answer": [str(value)], "mode": "number"}], explain,
                 params={"patch": patch, "axis": axis, "absolute": absolute})


sobel_response.gen_spec.meta.update(template_revision="sobel-direction-response-1", author_difficulty=3,
                                   display_params=["patch", "axis", "absolute"])
