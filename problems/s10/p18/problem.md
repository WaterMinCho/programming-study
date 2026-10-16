# p18. 강아지 소리 바꾸기 (반환값 · 4점)

아래 `Animal` 클래스가 이미 작성되어 있습니다(시작 코드에 포함).

```python
class Animal:
    def speak(self):
        return "Animal speaks"

    def move(self):
        return "Animal moves"
```

`Animal` 을 **상속받는** `Dog` 클래스를 정의하세요.

- `speak()` 를 **재정의(오버라이딩)** 하여 문자열 `Woof!` 를 **반환**합니다.
- `move()` 는 재정의하지 않습니다(부모의 것을 그대로 씁니다).
- `print` 로 출력하는 것이 아니라 `return` 으로 돌려줘야 합니다.
- `Animal` 클래스는 고치지 않습니다.

## 입출력 예

| 호출 | 반환값 |
|---|---|
| `Dog().speak()` | `'Woof!'` |
| `Animal().speak()` | `'Animal speaks'` |
| `Dog().move()` | `'Animal moves'` |

`Dog().speak()` 는 `d = Dog()` 로 객체를 만든 뒤 `d.speak()` 를 호출한 것과 같습니다.
