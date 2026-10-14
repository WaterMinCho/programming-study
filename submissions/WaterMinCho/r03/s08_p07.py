N = int(input())

numbers = []

for _ in range(N):
    numbers.append(int(input()))
    
max_value = numbers[0]
min_value = numbers[0]

for num in numbers:
    if num > max_value:
        max_value = num
    if num < min_value:
        min_value = num
        
print("최댓값:", max_value)
print("최솟값:", min_value)
    
