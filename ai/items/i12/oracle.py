# -*- coding: utf-8 -*-
"""공개 지문의 수치를 별도 계산해 생성기 답과 대조함."""
from __future__ import annotations
import itertools
import re
from fractions import Fraction

def _calc_i12_g01(question: str) -> list[str]:
    """구간별로 공간 묶음과 채널 목록을 갱신해 마지막 좌표를 셈."""
    height, width, blocks, channels = map(int, _fields('공간 (\\d+)×(\\d+)에서 크기를 유지하는 합성곱과 기본 MaxPool2d\\(2\\)를 (\\d+)구간 적용합니다\\. 첫 풀링 전 출력 채널은 (\\d+)이고 다음 구간마다 두 배로 정했습니다\\. 마지막 특징을 한 장씩 펼치면 값은 ____ 개입니다\\.', question))
    _positive(height, width, blocks, channels)
    rows, cols = (list(range(height)), list(range(width)))
    channel_ids = list(range(channels))
    for block in range(blocks):
        if block:
            channel_ids = channel_ids + channel_ids
        rows = [rows[pos:pos + 2] for pos in range(0, len(rows) - 1, 2)]
        cols = [cols[pos:pos + 2] for pos in range(0, len(cols) - 1, 2)]
        if not rows or not cols:
            raise ValueError('양의 공간 크기를 만드는 입력만 지원함.')
    count = sum((1 for _ in itertools.product(channel_ids, rows, cols)))
    return [str(count)]

def _calc_i12_g02(question: str) -> list[str]:
    """단위 입력 뒤에 0을 넣는 이동 평균을 분수로 누적함."""
    raw_rho, raw_lag, raw_power = _fields('분수로 답해도 됩니다\\. 이전 기록 비율 rho=(\\d+/\\d+)인 지수 이동 평균에서 이번 값의 무게는 1−rho입니다\\. (\\d+)번 전 값의 절대 무게 \\(1−rho\\)×rho\\^(\\d+)는 ____ 입니다\\.', question)
    rho, lag = (Fraction(raw_rho), int(raw_lag))
    if not 0 <= rho <= 1 or lag != int(raw_power):
        raise ValueError('비율이나 시차 표기가 지원 범위를 벗어남.')
    state = Fraction(0)
    samples = [1] + [0] * lag
    for sample in samples:
        state = rho * state + (1 - rho) * sample
    return [str(state)]

def _calc_i12_g03(question: str) -> list[str]:
    """각 손실을 나머지 손실과 견줘 유일한 최솟값의 순서를 고름."""
    raw, = _fields('에폭을 1부터 셉니다\\. 검증 손실이 (\\[(?:\\d+(?:\\.\\d+)?)(?:, \\d+(?:\\.\\d+)?)*\\])라면 가장 작은 손실을 기록한 에폭은 ____ 입니다\\.', question)
    losses = [Fraction(value.strip()) for value in raw[1:-1].split(',')]
    if len(set(losses)) != len(losses):
        raise ValueError('공개 명세의 서로 다른 손실 조건을 벗어남.')
    winners = [index for index, loss in enumerate(losses, 1) if all((loss <= other for other in losses))]
    if len(winners) != 1:
        raise ValueError('최솟값의 에폭을 하나로 정할 수 없음.')
    return [str(winners[0])]

def _calc_i12_g04(question: str) -> list[str]:
    """위치마다 weight와 bias의 원소 목록을 따로 셈."""
    channels, locations = map(int, _fields('채널 (\\d+)개인 BatchNorm2d를 (\\d+)위치에 하나씩 독립 생성합니다\\. affine=True, bias=True이며 running 통계는 학습 파라미터에서 제외합니다\\. weight와 bias의 원소 수는 합쳐 ____ 개입니다\\.', question))
    _positive(channels, locations)
    objects = [{'weight': list(range(channels)), 'bias': list(range(channels))} for _ in range(locations)]
    return [str(sum((len(obj['weight']) + len(obj['bias']) for obj in objects)))]

def _calc_i12_g05(question: str) -> list[str]:
    """격자의 각 칸을 세어 가린 칸의 비율을 구함."""
    height, width, erased_h, erased_w = map(int, _fields('분수로 답해도 됩니다\\. 높이 (\\d+), 너비 (\\d+)인 이미지에서 이번에 높이 (\\d+), 너비 (\\d+)의 직사각형을 가렸습니다\\. 지운 공간 넓이÷원본 공간 넓이는 ____ 입니다\\.', question))
    _positive(height, width, erased_h, erased_w)
    if erased_h > height or erased_w > width:
        raise ValueError('이미지 안에 들어가는 직사각형만 지원함.')
    total = erased = 0
    for row in range(height):
        for col in range(width):
            total += 1
            erased += row < erased_h and col < erased_w
    return [str(Fraction(erased, total))]

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

def i12_g01(params: dict) -> list[str]:
    side = _integer(params, 'side')
    first = _integer(params, 'first')
    depth = _integer(params, 'depth')
    question = f'공간 {side}×{side}에서 크기를 유지하는 합성곱과 기본 MaxPool2d(2)를 {depth}구간 적용합니다. 첫 풀링 전 출력 채널은 {first}이고 다음 구간마다 두 배로 정했습니다. 마지막 특징을 한 장씩 펼치면 값은 ____ 개입니다.'
    return _calc_i12_g01(question)

def i12_g02(params: dict) -> list[str]:
    age = _integer(params, 'age', 0)
    raw_rho = params['rho']
    if not isinstance(raw_rho, str):
        raise TypeError('rho에 분수 문자열을 전달함.')
    rho = Fraction(raw_rho)
    if not 0 <= rho <= 1:
        raise ValueError('rho의 지원 범위를 벗어남.')
    text = f'{rho.numerator}/{rho.denominator}'
    question = f'분수로 답해도 됩니다. 이전 기록 비율 rho={text}인 지수 이동 평균에서 이번 값의 무게는 1−rho입니다. {age}번 전 값의 절대 무게 (1−rho)×rho^{age}는 ____ 입니다.'
    return _calc_i12_g02(question)

def i12_g03(params: dict) -> list[str]:
    if not isinstance(params, dict):
        raise TypeError('params에 dict를 전달함.')
    losses = params['losses']
    if not isinstance(losses, list) or not losses:
        raise TypeError('losses에 비어 있지 않은 정수 배열을 전달함.')
    if any((type(value) is not int or value < 0 for value in losses)):
        raise ValueError('losses의 지원 범위를 벗어남.')
    text = ', '.join((f'{value // 100}.{value % 100:02d}' for value in losses))
    question = f'에폭을 1부터 셉니다. 검증 손실이 [{text}]라면 가장 작은 손실을 기록한 에폭은 ____ 입니다.'
    return _calc_i12_g03(question)

def i12_g04(params: dict) -> list[str]:
    channels = _integer(params, 'channels')
    places = _integer(params, 'places')
    question = f'채널 {channels}개인 BatchNorm2d를 {places}위치에 하나씩 독립 생성합니다. affine=True, bias=True이며 running 통계는 학습 파라미터에서 제외합니다. weight와 bias의 원소 수는 합쳐 ____ 개입니다.'
    return _calc_i12_g04(question)

def i12_g05(params: dict) -> list[str]:
    height = _integer(params, 'height')
    width = _integer(params, 'width')
    erase_h = _integer(params, 'erase_h')
    erase_w = _integer(params, 'erase_w')
    question = f'분수로 답해도 됩니다. 높이 {height}, 너비 {width}인 이미지에서 이번에 높이 {erase_h}, 너비 {erase_w}의 직사각형을 가렸습니다. 지운 공간 넓이÷원본 공간 넓이는 ____ 입니다.'
    return _calc_i12_g05(question)
