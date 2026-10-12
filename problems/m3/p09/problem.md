# p09. 넘치지 않는 물탱크 (출력 · 6점)

아래 `Tank` 클래스가 이미 작성되어 있습니다(시작 코드에 포함).

```python
class Tank:
    def __init__(self, name):
        self.name = name
        self.amount = 0

    def fill(self, liters):
        self.amount += liters
        print(self.name, "채움", self.amount)

    def fill_all(self, plan):
        for liters in plan:
            self.fill(liters)
        print(self.name, "완료", self.amount)
```

`Tank` 를 **상속받는** `SafeTank` 클래스를 정의하세요.

1. 생성자는 이름 `name` 과 용량 `capacity` 를 받습니다. `name` 과 `amount` 는 부모의 `__init__` 이 저장하게 하고, `capacity` 는 같은 이름의 인스턴스 변수에 저장합니다.
2. `fill(liters)` 를 재정의합니다. 지금 들어 있는 양에 `liters` 를 더한 값이 `capacity` 보다 **크면** `amount` 를 바꾸지 않고 `ValueError("넘침")` 예외를 일으킵니다(출력 없음). 그렇지 않으면 부모의 `fill()` 을 실행합니다. 용량을 꼭 맞게 채우는 것은 넘치는 것이 아닙니다.
3. `room()` 메서드를 추가합니다. 더 넣을 수 있는 양인 `capacity - amount` 를 **반환**합니다.
4. `fill_all()` 은 새로 정의하지 않고 부모의 것을 씁니다.

## 제한 사항

- `capacity` 는 0 이상 1000 이하의 정수이고 `liters` 는 1 이상 1000 이하의 정수입니다.
- `Tank` 클래스는 고치지 않습니다. 채점할 때는 아래와 같은 테스트 코드가 객체를 만들어 메서드를 호출하고, 예외는 테스트 코드가 `try-except` 로 받아 출력합니다.
- 제출하면 `Tank` 의 `__init__`, `fill()`, `fill_all()` 을 다른 함수로 바꿔 놓은 테스트도 함께 돌립니다. `SafeTank` 가 부모의 메서드를 호출하지 않고 부모의 코드를 옮겨 적은 답은 이 테스트에서 오답 처리됩니다.
- 예외의 종류는 `ValueError`, 메시지는 `넘침` 이어야 합니다.

## 테스트 코드와 출력 예

```python
t = SafeTank("A", 10)
t.fill(4)
t.fill(6)
print(t.room())
```

```
A 채움 4
A 채움 10
0
```

```python
t = SafeTank("B", 10)
try:
    t.fill_all([4, 5, 3, 1])
except ValueError as e:
    print("오류:", e)
print(t.amount, t.room())
```

```
B 채움 4
B 채움 9
오류: 넘침
9 1
```

두 번째 예에서는 세 번째 값 3 을 넣을 때 예외가 나서 `fill_all()` 의 반복이 거기서 끝나므로 `B 완료` 줄은 출력되지 않습니다.
