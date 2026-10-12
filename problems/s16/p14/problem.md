# p14. 주어진 스택 클래스 사용하기 (빈칸 채우기 · 4점)

`Stack` 클래스가 주어져 있습니다. 이 클래스의 객체를 만들고, 입력받은 단어를 스택에 넣어 리스트를 출력한 뒤, 그 단어를 다시 꺼내고 리스트를 한 번 더 출력하는 프로그램입니다.
빈칸(`____`) 3곳을 채워 프로그램을 완성하세요.

- 넣고 꺼내는 일은 `Stack` 클래스의 메서드로 합니다.
- 객체를 만든 직후에 리스트에 무엇이 들어 있는지는 `__init__` 에서 확인합니다.
- 빈칸만 채웁니다. 다른 줄을 고치거나 줄을 추가하면 오답 처리됩니다.

```python
class Stack:
    def __init__(self):
        self.stack = ['두산', '로키', '부트']

    def push(self, data):
        self.stack.append(data)

    def pop(self):
        if not self.is_empty():
            return self.stack.pop()
        return

    def is_empty(self):
        return len(self.stack) == 0

    def peak(self):
        if not self.is_empty():
            return self.stack[-1]
        return

    def status_stack(self):
        return self.stack


word = input()
s = ____
s.____(word)
print(s.status_stack())
s.____()
print(s.status_stack())
```

## 입출력 예

입력

```
캠프
```

출력

```
['두산', '로키', '부트', '캠프']
['두산', '로키', '부트']
```
