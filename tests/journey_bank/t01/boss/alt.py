import heapq


def solution(nums, k):
    return sum(heapq.nlargest(k, nums))
