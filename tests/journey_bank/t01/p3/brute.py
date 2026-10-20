"""1-3 이름 뒤집기 완전 탐색. 뒤에서부터 한 글자씩 붙임."""


def brute_ok(name):
    return len(name) <= 5000


def solution(name):
    out = ""
    for i in range(len(name) - 1, -1, -1):
        out += name[i]
    return out
