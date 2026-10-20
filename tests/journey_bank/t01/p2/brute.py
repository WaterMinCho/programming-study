"""1-2 가장 큰 물통 완전 탐색. 값마다 그보다 큰 값이 없는지 모두 봄."""


def brute_ok(nums):
    return len(nums) <= 2000


def solution(nums):
    for x in nums:
        if all(y <= x for y in nums):
            return x
