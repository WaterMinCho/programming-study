def solution(nums, k):
    return sum(sorted(nums, reverse=True)[:k])
