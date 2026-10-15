def solution(student):
    answer = 0
    sum = 0
    for score in student['scores']:
        sum += score
    answer = sum / len(student['scores'])
    return answer
