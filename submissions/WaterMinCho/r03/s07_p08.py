def solution(scores):
    answer = 0
    average = 0
    sum = 0
    for score in scores:
        sum += score
    average = sum / len(scores)
    for score in scores:
        if average <= score:
            answer = answer + 1
    return answer
