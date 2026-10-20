"""1-2 가장 큰 물통 제한사항 검사. validate 는 solution 의 인자를 받아 어긴 줄의 문구를, 다 지키면 None 을 돌려줌."""


def validate(nums):
    if not 1 <= len(nums) <= 20000:
        return "1번 줄: nums 의 길이가 %d" % len(nums)
    for x in nums:
        if not -1000 <= x <= 1000:
            return "2번 줄: 원소 %d" % x
    return None
