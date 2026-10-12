# p16. 리스트로 만드는 덱 (빈칸 채우기 · 6점)

`collections` 의 `deque` 를 쓰지 않고 리스트만으로 덱(양방향 큐)을 구현한 `Deque` 클래스입니다. 빈칸(`____`) 3곳을 채워 클래스를 완성하세요.

| 메서드 | 하는 일 |
|---|---|
| `push_front(x)` | `x` 를 덱의 앞에 넣습니다 |
| `push_back(x)` | `x` 를 덱의 뒤에 넣습니다 |
| `pop_front()` | 덱의 앞에서 값을 제거하고 반환합니다. 비어 있으면 `-1` 을 반환합니다 |
| `pop_back()` | 덱의 뒤에서 값을 제거하고 반환합니다. 비어 있으면 `-1` 을 반환합니다 |

- `self.items` 는 리스트이고, 리스트의 앞(인덱스 0)이 덱의 앞입니다.
- 빈칸만 채웁니다. 다른 줄을 고치거나 줄을 추가하면 오답 처리됩니다.

```python
class Deque:
    def __init__(self):
        self.items = []

    def push_front(self, x):
        self.items.____

    def push_back(self, x):
        self.items.____(x)

    def pop_front(self):
        if len(self.items) == 0:
            return -1
        return self.items.____

    def pop_back(self):
        if len(self.items) == 0:
            return -1
        return self.items.pop()
```

## 테스트 코드와 출력 예

```python
d = Deque()
d.push_back(1)
d.push_back(2)
d.push_front(3)
print(d.items)
print(d.pop_front())
print(d.pop_back())
print(d.items)
```

```
[3, 1, 2]
3
2
[1]
```

```python
d = Deque()
print(d.pop_front())
print(d.pop_back())
print(d.items)
```

```
-1
-1
[]
```
