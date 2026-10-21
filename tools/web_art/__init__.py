# -*- coding: utf-8 -*-
"""웹 면접 준비 그림 도구. 학습 페이지·사슬 절·미션 해설 그림은 알고리즘 여행의 tools/journey_art/draw.py 로 그리고,
페이지·미션마다 둔 스크립트(tools/web_art/l03.py, w03.py)가 web/<종류>/<id>/assets/ 에 씀.

이 파일은 Pillow 없이도 import 되게 이름 규칙과 한도만 둠. 그림 한 장의 한도(GIF 300KB, PNG 200KB, 프레임 12개, 프레임
800~2500ms, 논리 폭 560px)는 journey_art 와 같고, 합계 한도만 web/ 전체 6MB 로 다름. tools/verify_web.py 가 같은 값을 봄.
그림 이름은 설계 4.5절대로 페이지 그림 l01-1, 사슬 절 그림 3a-1, 미션 해설 그림 w03-1 꼴임.
"""
import re

from tools.journey_art import COLORS, KB, SCALE  # noqa: F401
from tools.journey_art import LIMITS as _JOURNEY_LIMITS

LIMITS = dict(_JOURNEY_LIMITS, total_bytes=6 * 1024 * KB)  # web/ 전체 그림 합계

NAMES = {
    "page": re.compile(r"^l\d{2}-\d{1,2}\Z"),  # 학습 페이지 그림. l01-1
    "section": re.compile(r"^\d{1,2}[a-z]-\d{1,2}\Z"),  # 사슬 절 그림. 3a-1
    "mission": re.compile(r"^w\d{2}-\d{1,2}\Z"),  # 미션 해설 그림. w03-1
}


def name_kind(name):
    """그림 이름이 어느 규칙인지. 맞는 규칙이 없으면 None."""
    for kind, pattern in NAMES.items():
        if pattern.match(name):
            return kind
    return None


def owner_of(name):
    """그림 이름이 가리키는 페이지·절·미션. l01-1 은 ("page", "l01"), 3a-1 은 ("section", "3a"), w03-1 은 ("mission", "w03").
    규칙에 맞지 않으면 None."""
    kind = name_kind(name)
    if kind is None:
        return None
    return kind, name.rsplit("-", 1)[0]
