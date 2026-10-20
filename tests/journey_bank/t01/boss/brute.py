"""1-B 물통 정리 완전 탐색. 가장 큰 값을 k번 꺼내 더함."""


def brute_ok(nums, k):
    return len(nums) <= 2000


def solution(nums, k):
    rest = list(nums)
    total = 0
    for _ in range(k):
        best = max(rest)
        rest.remove(best)
        total += best
    return total
