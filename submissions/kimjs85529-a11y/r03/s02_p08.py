def solution(seconds):
    answer = ""
    a = seconds // 60
    b = seconds % 60
    
    answer = f"{a}분 {b}초"
    return answer
