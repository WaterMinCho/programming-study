def solution(n):
    # 여기에 코드를 작성하세요
    answer = []
    for num in range(0, n+1):
        if num % 2 == 0:
            answer.append(num**2)
    
    return iter(answer)
