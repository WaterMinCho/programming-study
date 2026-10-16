# 여기에 코드를 작성하세요
a = int(input())
c=str(input())
b= int(input())
if c == "+":
    print(f"{a} + {b} = {a+b}")
elif c == "-":
    print(f"{a} - {b} = {a-b}")
elif c == "*":
    print(f"{a} * {b} = {a*b}")
elif c == "/":
    print(f"{a} / {b} = {a/b}")
else:
    print("지원하지 않는 연산자입니다.")
