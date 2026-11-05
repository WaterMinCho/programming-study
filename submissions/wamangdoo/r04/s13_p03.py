a = int(input())
b = int(input())

try:
    result = a / b
    print(a, "/", b, "=", result)
except ZeroDivisionError:
    print("0으로 나눌 수 없습니다")
