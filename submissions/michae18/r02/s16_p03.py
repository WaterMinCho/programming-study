def solution(commands):
    answer = []
    for num in commands:
        if commands:
            if num == 0:
                if answer:
                    answer.pop()
            else:
                answer.append(num)
        else:
            break
    return answer
