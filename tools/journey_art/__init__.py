# -*- coding: utf-8 -*-
"""해설 그림 도구. draw.py 가 그리고 render.py 가 던전 스크립트(d01.py …)를 돌려 dungeons/<던전>/assets/ 에 씀.

이 파일은 Pillow 없이도 import 되게 색 상수와 한도만 둠. 검증 도구가 같은 한도를 볼 때 여기서 가져감.
"""
import re

SCALE = 2  # 논리 픽셀 하나를 파일에서 몇 픽셀로 그리는지. 화면은 픽셀 / SCALE 크기로 보여 줌

# gui/theme.py 의 EDITOR 값을 그대로 옮긴 것. tests/test_journey_art.py 가 같은지 봄
COLORS = {
    "bg": "#253747", "gutter": "#203140", "edge": "#3a5166", "selection": "#3d6187",
    "ink": "#e0e8f0", "line_no": "#7d91a4",
    "keyword": "#ba9cdc", "def": "#e8e078", "builtin": "#6cc4dc", "string": "#7fc18e", "comment": "#8497a9", "number": "#e092c4",
    "decorator": "#f0a868", "self": "#f08c8c", "missing": "#ff8a80",
}

KB = 1024
LIMITS = {
    "gif_bytes": 300 * KB,  # GIF 파일 하나
    "png_bytes": 200 * KB,  # PNG 파일 하나
    "frames": 12,  # GIF 프레임 수
    "ms_min": 800, "ms_max": 2500,  # 프레임 하나의 시간
    "width": 560,  # 논리 폭. 파일은 width * SCALE
    "total_bytes": 2560 * KB,  # 던전 assets/ 합계
}

NAME = re.compile(r"^\d{1,2}-(\d|b)[a-z]$")  # 그림 이름: <던전>-<문제 번호 또는 b><글자>. 1-1a, 1-ba
