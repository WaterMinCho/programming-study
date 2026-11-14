# -*- coding: utf-8 -*-
"""평행이동의 수치와 조회 방향을 바꾸는 한 문항군임."""
from aiprep.gen import blank, gen

TEMPLATE_REVISION = "affine-translation-1"


@gen("a02-g01", unit="a2d", level=2, tags=["아핀 좌표", "정방향과 역조회"],
     ref=["응용 2차시 슬 p7", "응용 2차시 노트북 02 [38]"], facts=["FA02-d1"],
     basis="lecture-formula", step="a2d/3", family="affine-coordinate-direction", core=False, prio=2)
def translation(r):
    """원본→출력 행렬과 주어진 점에서 묻는 방향의 x/y 좌표를 계산함."""
    x, y, tx, ty = r.int(-8, 8), r.int(-8, 8), r.int(-4, 4), r.int(-4, 4)
    direction = r.pick(("source_to_destination", "destination_to_source"))
    forward = direction == "source_to_destination"
    xx, yy = (x + tx, y + ty) if forward else (x - tx, y - ty)
    given, asked = ("원본", "출력") if forward else ("출력", "원본")
    sign = "+" if forward else "−"
    stem = ("왼쪽 위가 원점이며 x는 오른쪽, y는 아래로 증가합니다. "
            "원본→출력 행렬은 [[1, 0, %d], [0, 1, %d]]입니다.\n\n"
            "%s 점 (%d, %d)에 대응하는 %s 좌표를 구하세요. x는 ____ 이고 y는 ____ 입니다.\n\n"
            "화면 크기를 정하지 않은 좌표 계산입니다. 음수도 계산한 값으로 답하세요.") % (tx, ty, given, x, y, asked)
    explain = ("이동만 있는 행렬에서 %s 좌표는 이동량을 %s 구합니다. "
               "x = %d %s (%d) = %d, y = %d %s (%d) = %d입니다. "
               "결과는 (%d, %d)입니다. 픽셀을 읽을 수 있는지는 영상 크기와 경계 처리 방식을 보고 따로 판단합니다.") % (
                   asked, "더해" if forward else "빼서", x, sign, tx, xx, y, sign, ty, yy, xx, yy)
    return blank(stem, [{"answer": [str(xx)], "mode": "number"}, {"answer": [str(yy)], "mode": "number"}],
                 explain, params={"point": [x, y], "translation": [tx, ty], "direction": direction})


translation.gen_spec.meta.update(template_revision=TEMPLATE_REVISION, author_difficulty=2,
                                 display_params=["point", "translation", "direction"])
