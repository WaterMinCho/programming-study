# 여기에 코드를 작성하세요

num1 = int(input())
a = input()
num2 = int(input())
operation = ['+', '-', '*', '/']
for op in operation:
    if a == op:
        if op == '+':
            result = num1 + num2
        elif op == '-':
            result = num1 - num2
        elif op == '*':
            result = num1 * num2
        elif op == '/':
            result = num1 / num2
        else:
            print('지원하지 않는 연산자입니다')
        print(f'{num1} {a} {num2} = {result}')
