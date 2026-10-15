def solution(json_string, key):
    answer = None
    dic = eval(json_string)
    answer = dic.get(key)
    return answer
