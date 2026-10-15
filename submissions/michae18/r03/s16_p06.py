def solution(s):
    list1 = []
    answer = True
    for i in s:
        if i == '(':
            list1.append(i)
            print('추가:',list1)
        if i == ')':
            if len(list1) != 0:
                list1.pop()
                print('제거 상태:',list1)
            else:
                answer = False
        #elif len(i) == 0:
         #   answer = False
          #  print('answer)
           # return False
    print('현재 상태:',list1)
    if len(list1) is not 0:
            answer = False
            #print(answer)
            return answer
#    print(answer)
    return answer
    
