def solution(a, b):
    answer = 0
    if a > b:
        answer = a - b
    elif a < b:
        answer = b - a
    elif a == b:
        answer = 0
    return answer
