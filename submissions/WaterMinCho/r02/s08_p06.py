def solution(numbers):
    max_value = numbers[0]
    answer = 0
    for i in range(len(numbers)):
        if numbers[i] > max_value:
            max_value = numbers[i]
            answer = i
    
    
    return answer
