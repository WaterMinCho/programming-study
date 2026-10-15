def solution(clicks):
    answer = 1
    
    for button in clicks:
        if button == "+":
            if answer < 10:
                answer += 1
        elif button == "-":
            if answer > 1:
                answer -= 1
        elif button == "초기화":
            answer = 1
            
    return answer
