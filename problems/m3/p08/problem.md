# p08. 건너뛰며 꺼내는 이터레이터 (빈칸 채우기 · 6점)

리스트 `items` 의 요소를 첫 요소부터 `step` 칸씩 건너뛰며 하나씩 돌려주는 이터레이터 클래스 `Skip` 입니다. `Skip([10, 20, 30, 40, 50], 2)` 는 `10`, `30`, `50` 을 차례로 돌려주고, 더 돌려줄 요소가 없으면 `StopIteration` 예외를 일으킵니다. 빈칸(`____`) 3곳을 채워 클래스를 완성하세요.

```python
class Skip:
    def __init__(self, items, step):
        self.items = items
        self.step = step
        self.index = 0

    def __iter__(self):
        return self

    def ____(self):
        if self.index ____ len(self.items):
            ____
        value = self.items[self.index]
        self.index += self.step
        return value
```

- 첫 번째 빈칸은 `next()` 가 호출될 때 실행되는 메서드의 이름입니다.
- 두 번째 빈칸은 비교 연산자입니다. `index` 가 리스트의 범위를 벗어났는지 확인합니다.
- 세 번째 빈칸에는 값을 다 돌려주었다는 신호인 `StopIteration` 예외를 일으키는 문장을 적습니다.
- `step` 은 1 이상의 정수이고 `items` 는 비어 있을 수 있습니다.
- 클래스만 완성하면 됩니다. 채점할 때는 아래와 같은 테스트 코드가 객체를 만들어 사용합니다.
- **빈칸만** 채웁니다. 다른 줄을 고치거나 줄을 추가하면 오답 처리됩니다.

## 테스트 코드와 출력 예

```python
for x in Skip([10, 20, 30, 40, 50], 2):
    print(x)
```

```
10
30
50
```

```python
it = Skip(["a", "b", "c"], 1)
print(next(it), next(it), next(it))
try:
    next(it)
except StopIteration:
    print("끝")
```

```
a b c
끝
```
