# p18. 비어 있으면 -1 을 돌려주는 스택 (빈칸 채우기 · 4점)

리스트를 이용해 스택을 구현한 `Stack` 클래스입니다. 빈칸(`____`) 3곳을 채워 클래스를 완성하세요.

| 메서드 | 하는 일 |
|---|---|
| `push(x)` | `x` 를 스택에 넣습니다 |
| `pop()` | 스택의 가장 위의 값을 제거하고 반환합니다. 비어 있으면 `-1` 을 반환합니다 |
| `top()` | 스택의 가장 위에 있는 값을 제거하지 않고 반환합니다. 비어 있으면 `-1` 을 반환합니다 |
| `is_empty()` | 스택이 비어 있으면 `True`, 아니면 `False` 를 반환합니다 |

- 리스트의 뒤가 스택의 위입니다.
- 빈칸만 채웁니다. 다른 줄을 고치거나 줄을 추가하면 오답 처리됩니다.

```python
class Stack:
    def __init__(self):
        self.stack = []

    def push(self, x):
        self.stack.append(x)

    def pop(self):
        if self.is_empty():
            return -1
        return self.stack.____

    def top(self):
        if self.is_empty():
            return -1
        return self.stack[____]

    def is_empty(self):
        return ____
```

## 테스트 코드와 출력 예

```python
s = Stack()
s.push(4)
s.push(8)
print(s.top())
print(s.pop())
print(s.stack)
```

```
8
8
[4]
```

```python
s = Stack()
print(s.pop())
print(s.top())
print(s.is_empty())
```

```
-1
-1
True
```
