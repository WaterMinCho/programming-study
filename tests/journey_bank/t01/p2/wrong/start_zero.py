def solution(nums):
    best = 0
    for x in nums:
        best = max(best, x)
    return best
