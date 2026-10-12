# p16. range 처럼 세는 이터레이터 클래스 (출력 · 8점)

내장 `range()` 처럼 `start` 부터 `step` 씩 건너뛰며 `stop` 앞까지의 정수를 하나씩 돌려주는 이터레이터 클래스 `MyRange` 를 작성하세요.

- `MyRange(start, stop, step)` 으로 객체를 만듭니다. `step` 을 생략하면 1 로 봅니다.
- `__iter__` 와 `__next__` 메서드를 구현합니다. `__iter__` 는 자기 자신을 돌려줍니다.
- `stop` 은 돌려주지 않습니다. `MyRange(0, 6, 2)` 는 0, 2, 4 를 돌려줍니다.
- `step` 이 음수이면 값이 줄어드는 방향으로 세고, 값이 `stop` 보다 큰 동안만 돌려줍니다. `MyRange(10, 0, -3)` 은 10, 7, 4, 1 을 돌려줍니다.
- 돌려줄 값이 없으면 `next()` 에서 `StopIteration` 예외가 나야 합니다. `MyRange(5, 1, 1)` 처럼 처음부터 돌려줄 값이 없는 경우에도 첫 `next()` 에서 이 예외가 납니다.
- `start`, `stop`, `step` 은 정수이고 `step` 은 0 이 아닙니다.

## 테스트 코드와 출력 예

```python
for x in MyRange(0, 5, 1):
    print(x)
```

```
0
1
2
3
4
```

```python
for x in MyRange(1, 10, 3):
    print(x, end=" ")
print("end")
for x in MyRange(10, 0, -3):
    print(x, end=" ")
print("end")
```

```
1 4 7 end
10 7 4 1 end
```

```python
r = MyRange(2, 5)
print(next(r))
print(next(r))
print(next(r))
try:
    next(r)
except StopIteration:
    print("stop")
```

```
2
3
4
stop
```
