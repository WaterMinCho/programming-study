def solution(robot, coding):
    answer = []
    both = len(robot & coding)
    either = len(robot | coding)
    
    only_one = len(robot ^ coding)
    
    answer = [both, either, only_one]
    return answer
