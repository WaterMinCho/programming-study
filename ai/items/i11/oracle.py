# -*- coding: utf-8 -*-
"""공개 지문의 수치를 별도 계산해 생성기 답과 대조함."""
from __future__ import annotations
import itertools
import json
import re

def _calc_i11_g01(question: str) -> list[str]:
    """패딩을 포함한 축에서 커널이 들어가는 시작점을 셈."""
    n, k, p, s = map(int, _fields('dilation=1인 Conv2d의 입력 가로 (\\d+), 커널 가로 (\\d+), padding=(\\d+), stride=(\\d+)입니다\\. 출력 가로는 ____ 입니다\\.', question))
    _positive(n, k, s)
    padded = list(range(n + p + p))
    windows = []
    for start in range(0, len(padded), s):
        if len(padded[start:start + k]) == k:
            windows.append(start)
    if not windows:
        raise ValueError('양의 출력 길이를 만드는 입력만 지원함.')
    return [str(len(windows))]

def _calc_i11_g02(question: str) -> list[str]:
    """출력 채널별 커널 좌표와 편향 자리를 따로 셈."""
    ci, co, k = map(int, _fields('groups=1, bias=True인 nn\\.Conv2d\\((\\d+), (\\d+), kernel_size=(\\d+)\\)의 학습 파라미터 수는 ____ 개입니다\\.', question))
    _positive(ci, co, k)
    weights = sum((1 for _ in itertools.product(range(co), range(ci), range(k), range(k))))
    biases = sum((1 for _ in range(co)))
    return [str(weights + biases)]

def _calc_i11_g03(question: str) -> list[str]:
    """기본 이동 간격으로 나눈 묶음에서 온전한 구역을 셈."""
    n, k = map(int, _fields('입력 가로가 (\\d+)이고 nn\\.MaxPool2d\\((\\d+)\\)를 씁니다\\. stride는 생략하고 padding=0, dilation=1, ceil_mode=False입니다\\. 출력 가로는 ____ 입니다\\.', question))
    _positive(n, k)
    cells = list(range(n))
    complete = [cells[start:start + k] for start in range(0, n, k) if len(cells[start:start + k]) == k]
    if not complete:
        raise ValueError('양의 출력 길이를 만드는 입력만 지원함.')
    return [str(len(complete))]

def _calc_i11_g04(question: str) -> list[str]:
    """한 샘플의 채널·행·열 좌표를 세고 배치 수를 남김."""
    raw, = _fields('입력 텐서 (\\[\\d+, \\d+, \\d+, \\d+\\])를 기본 nn\\.Flatten\\(\\)으로 펼치면 모양은 ____ 입니다\\.', question)
    batch, channels, height, width = json.loads(raw)
    _positive(batch, channels, height, width)
    count = sum((1 for _ in itertools.product(range(channels), range(height), range(width))))
    return [json.dumps([batch, count], ensure_ascii=False)]

def _fields(pattern: str, question: str) -> tuple[str, ...]:
    """견본의 문장 구조와 맞지 않는 입력을 거절함."""
    match = re.fullmatch(pattern, question.strip())
    if match is None:
        raise ValueError('공개 견본의 문장 구조와 일치하지 않음.')
    return match.groups()

def _positive(*values: int) -> None:
    if any((value <= 0 for value in values)):
        raise ValueError('양의 정수만 지원함.')

def _integer(params: dict, key: str, minimum: int=1) -> int:
    """명세의 정수 값을 읽고 지원 범위를 확인함."""
    if not isinstance(params, dict):
        raise TypeError('params에 dict를 전달함.')
    value = params[key]
    if type(value) is not int:
        raise TypeError(f'{key}에 정수를 전달함.')
    if value < minimum:
        raise ValueError(f'{key}의 지원 범위를 벗어남.')
    return value

def i11_g01(params: dict) -> list[str]:
    n = _integer(params, 'length')
    k = _integer(params, 'kernel')
    p = _integer(params, 'padding', 0)
    s = _integer(params, 'stride')
    question = f'dilation=1인 Conv2d의 입력 가로 {n}, 커널 가로 {k}, padding={p}, stride={s}입니다. 출력 가로는 ____ 입니다.'
    return _calc_i11_g01(question)

def i11_g02(params: dict) -> list[str]:
    ci = _integer(params, 'cin')
    co = _integer(params, 'cout')
    k = _integer(params, 'kernel')
    question = f'groups=1, bias=True인 nn.Conv2d({ci}, {co}, kernel_size={k})의 학습 파라미터 수는 ____ 개입니다.'
    return _calc_i11_g02(question)

def i11_g03(params: dict) -> list[str]:
    n = _integer(params, 'length')
    k = _integer(params, 'kernel')
    question = f'입력 가로가 {n}이고 nn.MaxPool2d({k})를 씁니다. stride는 생략하고 padding=0, dilation=1, ceil_mode=False입니다. 출력 가로는 ____ 입니다.'
    return _calc_i11_g03(question)

def i11_g04(params: dict) -> list[str]:
    shape = [_integer(params, key) for key in ('batch', 'channels', 'height', 'width')]
    question = f'입력 텐서 {shape}를 기본 nn.Flatten()으로 펼치면 모양은 ____ 입니다.'
    return _calc_i11_g04(question)
