"""1-B 물통 정리 입력 생성기. 함수는 (rng, **params) 를 받아 solution 의 인자 목록 하나를 돌려줌."""


def small(rng):
    nums = [rng.between(-5, 5) for _ in range(rng.between(1, 8))]
    return [nums, rng.between(1, len(nums))]


def fill(rng, n, k):
    return [[rng.between(-1000, 1000) for _ in range(n)], k]
