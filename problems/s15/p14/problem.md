# p14. next() 로 끝까지 꺼내기 (빈칸 채우기 · 6점)

리스트를 이터레이터로 바꾼 뒤, for 문 없이 `next()` 만으로 모든 요소를 번호와 함께 출력하는 프로그램입니다. 값이 다 떨어졌을 때 발생하는 예외를 처리해 반복을 끝내고, 꺼낸 개수를 출력합니다.
빈칸(`____`) 3곳을 채워 프로그램을 완성하세요.

```python
fruits = ["apple", "banana", "cherry"]
it = iter(fruits)
count = 0
while True:
    try:
        fruit = ____(it)
    except ____:
        ____
    count += 1
    print(count, fruit)
print("total:", count)
```

- 첫 번째 빈칸: 이터레이터에서 값을 하나 꺼내는 내장 함수
- 두 번째 빈칸: 꺼낼 값이 더 없을 때 첫 번째 빈칸의 함수가 일으키는 예외
- 세 번째 빈칸: `while True` 반복을 끝내는 문장
- **빈칸만** 채웁니다. 다른 줄을 고치거나 줄을 추가하면 오답 처리됩니다.

## 출력 예

```
1 apple
2 banana
3 cherry
total: 3
```
