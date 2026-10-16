def solution(path):
    answer = 0
    with open(path, "r", encoding="utf-8") as f:
        line = f.readlines()
    
    print(line)
    for i in line:
        answer += int(i)
    
    return answer
