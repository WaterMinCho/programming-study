def solution(numbers):
    answer = []
    for i in numbers:
        if i < 0:
            answer.append(i)
    return answer
