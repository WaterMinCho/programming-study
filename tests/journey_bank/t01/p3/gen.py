"""1-3 이름 뒤집기 입력 생성기. 함수는 (rng, **params) 를 받아 solution 의 인자 목록 하나를 돌려줌."""
from journey.gen import word


def small(rng):
    return [word(rng, 1, 8, alphabet="abc")]


def repeat(rng, n):
    return ["a" * n]


def letters(rng, n):
    return [word(rng, n, n, alphabet="abcdefghijklmnopqrstuvwxyz")]


def two(rng, n):
    return ["ab" * (n // 2)]
