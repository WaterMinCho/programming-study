arr = [3, 6, 9, 12, 15]
i = int(input())
j = int(input())
# 여기에 코드를 작성하세요
print("바꾸기 전:", arr)
temp = arr[i]
arr[i] = arr[j]
arr[j] = temp
print("바꾼 후:", arr)
