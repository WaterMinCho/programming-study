# p17. 제곱 제너레이터 함수 (출력 · 4점)

정수 `n` 을 받아 1 부터 `n` 까지 각 숫자의 제곱을 차례로 돌려주는 **제너레이터 함수** `square_gen(n)` 을 작성하세요.

- 값은 `yield` 로 하나씩 내보냅니다. 함수를 호출한 결과는 리스트가 아니라 제너레이터 객체여야 합니다(`type(gen).__name__` 이 `generator`).
- `n` 의 제곱까지 돌려줍니다. 값을 다 돌려준 뒤의 `next()` 에서는 `StopIteration` 예외가 납니다.
- `n` 이 0 이면 아무 값도 돌려주지 않습니다.

## 제한 사항
- 0 ≤ n ≤ 1000

## 테스트 코드와 출력 예

```python
gen = square_gen(999)
print(next(gen))
print(next(gen))
print(next(gen))
```

```
1
4
9
```

```python
for v in square_gen(5):
    print(v)
```

```
1
4
9
16
25
```

```python
gen = square_gen(3)
print(type(gen).__name__)
print(next(gen), next(gen), next(gen))
try:
    next(gen)
except StopIteration:
    print("stop")
```

```
generator
1 4 9
stop
```
