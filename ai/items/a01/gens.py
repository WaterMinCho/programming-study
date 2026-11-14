# -*- coding: utf-8 -*-
"""uint8 배열의 포화 덧셈과 순환 덧셈을 비교하는 문항군임."""
from aiprep.gen import blank, gen


@gen("a01-g01", unit="a1c", level=2, tags=["app.픽셀연산"],
     ref=["응용 1차시 노트북 01 [27]", "응용 1차시 노트북 01 [42]",
          "OpenCV 문서 Arithmetic Operations on Images"],
     facts=["FA01-c1"], basis="lecture-example", step="a1c/2",
     family="a01-b07", core=False, prio=2)
def uint8_add(r):
    """범위 안·최댓값·범위 초과의 위치와 배열 길이를 바꿔 두 결과를 물음."""
    totals = [r.int(0, 254), 255, r.int(256, 510)]
    if r.chance(0.5):
        totals.append(r.int(0, 510))
    r.shuffle(totals)
    a = [r.int(max(0, total - 255), min(255, total)) for total in totals]
    b = [total - left for total, left in zip(totals, a)]
    saturated = [min(255, total) for total in totals]
    wrapped = [total % 256 for total in totals]
    code = ("import cv2\nimport numpy as np\n\n"
            f"a = np.array([{a}], dtype=np.uint8)\n"
            f"b = np.array([{b}], dtype=np.uint8)\n"
            "p = cv2.add(a, b)\nq = a + b")
    stem = ("한 행짜리 흑백 이미지 두 개를 더합니다. 두 배열의 자료형은 uint8입니다.\n\n"
            f"```python\n{code}\n```\n\n"
            "p의 첫 행은 ____ 이고 q의 첫 행은 ____ 입니다. "
            "각 칸에 왼쪽부터 배열 값만 쓰세요. 예: [1, 2, 3].")
    explain = (f"자료형의 범위를 적용하기 전 합은 {totals}입니다. "
               f"cv2.add는 255를 넘는 합을 255로 제한해 p의 첫 행이 {saturated}입니다. "
               f"NumPy의 uint8 배열 덧셈은 256으로 나눈 나머지를 저장해 q의 첫 행이 {wrapped}입니다. "
               "합이 255 이하인 위치에서는 두 결과가 같습니다.")
    return blank(stem, [{"answer": [str(saturated)], "mode": "values"},
                        {"answer": [str(wrapped)], "mode": "values"}],
                 explain, params={"a": a, "b": b})


uint8_add.gen_spec.meta.update(template_revision="uint8-add-comparison-1", author_difficulty=2,
                              display_params=["a", "b"])
