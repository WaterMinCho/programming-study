# p17. 핸드폰과 스마트폰 (출력 · 6점)

전화번호와 색상을 저장하는 핸드폰(`Phone`) 클래스와, 이를 **상속받아** 제조사(`company`)를 추가한 스마트폰(`SmartPhone`) 클래스를 정의하세요.

## Phone 클래스

1. **생성자** `Phone(number, color)`: 전화번호와 색상을 인스턴스 변수 `number`, `color` 에 저장합니다.
2. **`showInfo()`**: 아래 형식으로 두 줄 출력합니다. (콜론 뒤에 공백 한 칸)
   ```
   전화번호: 010-1234-5678
   색상: 검정
   ```

## SmartPhone 클래스 (Phone 상속)

1. **생성자** `SmartPhone(number, color, company)`: 부모의 생성자로 `number`, `color` 를 저장하고, 제조사를 인스턴스 변수 `company` 에 저장합니다.
2. **`showInfo()`**: 부모의 `showInfo()` 가 출력하는 두 줄에 이어서 `회사: 값` 을 한 줄 더 출력합니다(총 세 줄).

- 클래스만 정의하면 됩니다. 채점할 때는 아래와 같은 테스트 코드가 객체를 만들어 메서드를 호출합니다.

## 테스트 코드와 출력 예

```python
phone = Phone("010-1234-5678", "검정")
print(phone.number)
print(phone.color)
phone.showInfo()
```

```
010-1234-5678
검정
전화번호: 010-1234-5678
색상: 검정
```

```python
apple = SmartPhone("010-1234-5678", "검정", "애플")
print(apple.company)
apple.showInfo()
```

```
애플
전화번호: 010-1234-5678
색상: 검정
회사: 애플
```

- 출력은 글자 하나까지 같아야 합니다. 메서드 이름은 대소문자까지 `showInfo` 로 씁니다.
