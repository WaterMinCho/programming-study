"""1-1 물통 합계 입력 생성기. 함수는 (rng, **params) 를 받아 solution 의 인자 목록 하나를 돌려줌."""


def small(rng):
    return [[rng.between(-5, 5) for _ in range(rng.between(1, 8))]]


def fill(rng, n):
    return [[rng.between(-1000, 1000) for _ in range(n)]]


def same(rng, n, value):
    return [[value] * n]
