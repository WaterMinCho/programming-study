def solution(scores):
    average = sum(scores) / len(scores)
    answer = 0
    for score in scores:
        if score >= average:
            answer += 1
    return answer
