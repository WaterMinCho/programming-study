def solution(nums):
    best = nums[0]
    for x in nums:
        if x > best:
            best = x
    return best
