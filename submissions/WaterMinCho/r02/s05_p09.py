first = int(input())
last = int(input())

# 여기에 코드를 작성하세요
for a in range(first,last+1):
    if a is not first:
        print()
    for b in range(1,10):
       print(f"{a} x {b} = {a*b}")
