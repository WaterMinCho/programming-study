"""1-1 물통 합계 완전 탐색. 앞에서부터 하나씩 꺼내 더함."""


def brute_ok(nums):
    return len(nums) <= 5000


def solution(nums):
    rest = list(nums)
    total = 0
    while rest:
        total += rest.pop()
    return total
