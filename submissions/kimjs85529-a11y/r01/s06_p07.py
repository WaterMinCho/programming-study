def solution(text):
    answer = 0
    
    for ch in text:
        if ch != " ":
            answer = answer + 1
            
    return answer
