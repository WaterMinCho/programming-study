# 3회차 미니 모의고사

> 프로그램(`python study.py`)에서 풀면 이 폴더의 `quiz.py` 와 `.py` 파일에 답이 자동으로 저장됩니다.

문항 18개(보강할 단원 18개) · 평균 레벨 1.8 · 단원: s14 4, s09 2, s10 2, s12 2, s01 1, s02 1, s05 1, s08 1, s15 1, s16 1, s19 1, s21 1

## s08_Q15 (자료구조와 알고리즘 · 출력 예측 · 3점)

다음 코드의 출력 결과를 그대로 적으세요.

```python
def fch(x):
    x["kim"] = 95
    x["park"] = 70

score = {"kim": 80, "lee": 90}
backup = score
fch(backup)
print(score)
print(len(score))
```

## s09_Q16 (클래스(1) · 출력 예측 · 3점)

다음 코드의 출력 결과를 그대로 적으세요.

```python
class Ticket:
    def __init__(self, seat, price):
        self.seat = seat
        self.price = price * 2

    def discount(self, price):
        self.price = self.price - price
        print(self.seat, self.price, price)

t = Ticket("A3", 500)
t.discount(100)
t.discount(50)
```

## s10_Q13 (클래스(2) · 출력 예측 · 3점)

다음 코드를 파일로 저장한 뒤 **직접 실행**했을 때의 출력 결과를 그대로 적으세요.

```python
def plus(a, b):
    return a + b


print("모듈 시작")

if __name__ == "__main__":
    print(plus(2, 3))

print(__name__)
```

## s12_Q6 (파일 처리 · 객관식 · 2점)

다음 코드를 실행했을 때의 결과로 옳은 것은?

```python
f = open("memo.txt", "w")
f.write("hello")
f.close()
f.write("bye")
```

1. `memo.txt` 에 `hellobye` 가 저장된다.
2. `memo.txt` 에 `hello` 가 저장되고, `bye` 는 조용히 무시된다.
3. `memo.txt` 에 `hello` 가 저장된 뒤, 마지막 줄에서 오류가 발생한다.
4. `f.close()` 가 파일을 삭제하므로 `memo.txt` 는 남지 않는다.

## s14_Q2 (정규표현식 · 객관식 · 2점)

정규식 `go{2,3}d` 를 `re.match` 로 조사했을 때 매치되는 문자열을 **모두 고르세요**.

1. `god`
2. `good`
3. `goood`
4. `gooood`

## s14_Q6 (정규표현식 · 객관식 · 2점)

컴파일 옵션에 대한 설명으로 옳지 **않은** 것은?

1. `re.IGNORECASE` 와 `re.I` 는 같은 옵션으로, 대소문자 구별 없이 매치되게 한다.
2. `re.DOTALL` 은 `.` 메타 문자가 줄바꿈 문자 `\n` 과도 매치되게 한다.
3. `re.MULTILINE` 은 `.` 메타 문자가 여러 줄에 걸쳐 매치되게 하는 옵션이다.
4. `re.VERBOSE` 를 쓰면 정규식 안에 줄바꿈과 주석을 넣어 읽기 쉽게 작성할 수 있다.

## s14_Q10 (정규표현식 · 출력 예측 · 3점)

다음 코드의 출력 결과를 그대로 적으세요.

```python
import re
p = re.compile("[a-z]+", re.I)
m = p.match("Hello World")
print(m)
print(m.group())
```

## s14_Q15 (정규표현식 · 출력 예측 · 3점)

다음 코드의 출력 결과를 그대로 적으세요. (`be` 와 `or` 사이의 공백은 2개입니다)

```python
import re
text = "to be  or"
print(len(re.findall(r"\s", text)))
p = re.compile(r"\S+")
for m in p.finditer(text):
    print(m.start(), m.end(), m.group())
```

## s16_Q11 (알고리즘(1) · 객관식 · 2점)

다음 두 세트에 대해 결과가 `{1, 2}` 가 되는 식은?

```python
a = {1, 2, 3, 3}
b = {3, 4}
```

1. `a & b`
2. `a | b`
3. `a - b`
4. `b - a`

## s19_Q5 (statsmodels·scikit-learn·SciPy · 객관식 · 2점)

SciPy 에서 함수의 값을 가장 작게 만드는 변수 값을 구하는 최적화 함수는?

1. `minimize()`
2. `optimize()`
3. `fit()`
4. `gradient()`

## s21_Q26 (파이썬 활용 심화(os·pathlib·JSON) · 객관식 · 2점)

API 에 대한 설명으로 옳지 **않은** 것은?

1. API 는 Application Programming Interface 의 줄임말이다.
2. API 는 프로그램 간에 데이터와 기능을 주고받을 수 있게 하는 인터페이스이다.
3. REST API 는 HTTP 프로토콜을 기반으로 JSON 형태의 데이터를 주고받는 방식이다.
4. REST API 로 받은 JSON 데이터는 파이썬 딕셔너리로 바꿀 수 없어 문자열 그대로 다뤄야 한다.

## s01_p05 (파이썬 소개 및 환경설정 · 빈칸 채우기 · 이름과 글자 구분하기 · 6점)

파일: `s01_p05.py`

아래 **출력 예**의 두 줄이 그대로 출력되도록 빈칸(`____`)을 채워 프로그램을 완성하세요.

- **빈칸만** 채웁니다. 다른 부분을 고치거나 줄을 추가하면 오답 처리됩니다.
- 첫째 줄에는 `print` 라는 글자 다섯 개가 그대로 출력되어야 합니다.

## 시작 코드

```python
print(____)
____("Hello")
```

## 출력 예

```
print
Hello
```

## s02_p08 (프로그래밍 기초 · 반환값 · 분과 초로 바꾸기 · 6점)

파일: `s02_p08.py`

초 단위 시간 `seconds` 가 정수로 주어질 때, 이를 `"M분 S초"` 형식의 **문자열로 반환** 하는 `solution` 함수를 완성하세요.

- 함수 이름과 매개변수는 바꾸지 않습니다. `def` 줄과 `return answer` 줄 사이에, `answer` 줄과 같은 칸(공백 4칸)에 맞춰 코드를 작성합니다.
- 구한 답을 `answer` 에 저장하면 `return answer` 줄이 그 값을 돌려줍니다. `print` 로 출력만 하면 오답입니다.
- `분` 과 다음 숫자 사이에는 공백이 한 칸 있고, 숫자와 `분`·`초` 사이에는 공백이 없습니다.
- 60분 이상이어도 시간 단위로 바꾸지 않습니다(3600초 → `"60분 0초"`).

## 제한 사항
- 0 ≤ `seconds` ≤ 100000

## 입출력 예

| seconds | 반환값 |
|---|---|
| `205` | `"3분 25초"` |
| `59` | `"0분 59초"` |
| `600` | `"10분 0초"` |

205초는 60초가 3번(180초) 들어가고 25초가 남으므로 `"3분 25초"` 입니다.

## s05_p08 (반복문 · 반환값 · 음수만 골라 담기 · 6점)

파일: `s05_p08.py`

정수가 담긴 리스트 `numbers` 가 주어질 때, 그중 음수만 원래 순서대로 담은 새 리스트를 반환하는 `solution` 함수를
완성하세요. 음수가 하나도 없으면 빈 리스트 `[]` 를 반환합니다.

- 함수 이름과 매개변수는 바꾸지 않습니다.
- `print` 로 출력하는 것이 아니라 `return` 으로 돌려줘야 합니다.
- 0 은 음수가 아닙니다.
- 리스트에 값을 추가할 때는 4차시에 배운 `append()` 를 사용합니다.

## 제한 사항
- `numbers` 의 길이는 1 이상 100 이하
- -1000 ≤ `numbers` 의 각 값 ≤ 1000

## 입출력 예

| numbers | 반환값 |
|---|---|
| `[5, -12, 0, -7, 30]` | `[-12, -7]` |
| `[1, 2, 3]` | `[]` |
| `[-1, -1, 4, -9]` | `[-1, -1, -9]` |

## s09_p06 (클래스(1) · 출력 · 드론 정보 관리 · 6점)

파일: `s09_p06.py`

다음 조건에 맞는 `Drone` 클래스를 정의하세요.

1. **생성자**는 모델(`model`), 무게(`weight`), 색상(`color`)을 차례로 받아 같은 이름의 인스턴스 변수에 저장하고, `드론 생성` 을 출력합니다.
2. **`info()`** 는 저장된 정보를 아래 형식으로 세 줄 출력합니다. (콜론 뒤에 공백 한 칸)
3. **`set_info(model, weight, color)`** 는 세 인스턴스 변수의 값을 전달받은 값으로 바꾸고, 아무것도 출력하지 않습니다.

- 클래스만 정의하면 됩니다. 채점할 때는 아래와 같은 테스트 코드가 객체를 만들어 메서드를 호출합니다.

## 테스트 코드와 출력 예

```python
d = Drone("매빅", 249, "회색")
d.info()
```

```
드론 생성
모델: 매빅
무게: 249
색상: 회색
```

```python
d = Drone("매빅", 249, "회색")
d.set_info("팬텀", 1380, "흰색")
d.info()
print(d.model, d.weight, d.color)
```

```
드론 생성
모델: 팬텀
무게: 1380
색상: 흰색
팬텀 1380 흰색
```

- 출력은 글자 하나까지 같아야 합니다(띄어쓰기, 콜론 포함).

## s10_p07 (클래스(2) · 빈칸 채우기 · 자전거 정보 출력 · 6점)

파일: `s10_p07.py`

탈것(`Vehicle`)을 상속받은 자전거(`Bicycle`) 클래스를 정의하고, **이 파일을 직접 실행했을 때만** 객체를 만들어 정보를 출력하는 프로그램입니다.
빈칸(`____`) 3곳을 채워 프로그램을 완성하세요.

- `Bicycle` 의 `__init__` 은 부모의 `__init__` 으로 `name`, `speed` 를 저장하고 `gears` 를 추가로 저장합니다.
- `Bicycle` 의 `info()` 는 **부모의 `info()`** 를 먼저 호출한 뒤 기어 수를 한 줄 더 출력합니다.
- 마지막 `if` 문은 이 파일이 **메인 모듈로 직접 실행될 때만** 참이 되도록 합니다. 다른 파일에서 import 되면 안쪽 코드가 실행되지 않습니다.
- **빈칸만** 채웁니다. 다른 줄을 고치거나 줄을 추가하면 오답 처리됩니다.

```python
class Vehicle:
    def __init__(self, name, speed):
        self.name = name
        self.speed = speed

    def info(self):
        print(self.name, self.speed)


class Bicycle(Vehicle):
    def __init__(self, name, speed, gears):
        super().__init__(____, speed)
        self.gears = gears

    def info(self):
        ____.info()
        print("기어:", self.gears)


if __name__ == "____":
    b = Bicycle("자전거", 25, 7)
    b.info()
```

## 출력 예 (직접 실행했을 때)

```
자전거 25
기어: 7
```

## s12_p03 (파일 처리 · 빈칸 채우기 · 명단 출력하기 · 6점)

파일: `s12_p03.py`

현재 폴더에 이름이 한 줄에 하나씩 적힌 `names.txt` 가 있습니다. 파일의 모든 줄을 리스트로 읽어 인원 수를 출력한 뒤, 이름을 한 줄에 하나씩 출력하는 프로그램입니다.
빈칸(`____`) 3곳을 채워 프로그램을 완성하세요.

- 첫 줄에 `인원: 3` 처럼 줄 수를 출력합니다. (`인원:` 뒤에 공백 한 칸)
- 그다음 줄부터 파일에 적힌 순서대로 이름을 출력합니다. 읽은 줄에는 줄바꿈 문자가 이미 들어 있으므로, 이름 사이에 빈 줄이 생기지 않게 출력해야 합니다.
- 빈칸만 채웁니다. 다른 줄을 고치거나 줄을 추가하면 오답 처리됩니다.

```python
with open("names.txt", "r", encoding="utf-8") as f:
    lines = f.____()

print("인원:", ____(lines))
for line in lines:
    print(line, end=____)
```

## 입출력 예

`names.txt` 의 내용이 다음과 같을 때

```
민수
지영
현우
```

출력

```
인원: 3
민수
지영
현우
```

## s15_p05 (고급 함수 · 빈칸 채우기 · 제너레이터 두 가지 방법 · 6점)

파일: `s15_p05.py`

제너레이터를 함수로 한 번, 표현식으로 한 번 만드는 프로그램입니다. 빈칸(`____`) 2곳을 채워 완성하세요.

```python
def countdown(start):
    n = start
    while n > 0:
        ____ n
        n = n - 1


gen = countdown(3)
print(next(gen))
print(next(gen))
print(next(gen))

squares = ____
print(type(squares))
print(next(squares))
for s in squares:
    print(s)
```

- `countdown(start)` 는 `start` 부터 1 까지 값을 하나씩 돌려주는 제너레이터 함수입니다. 첫 번째 빈칸에는 값을 하나 돌려주고 멈추는 키워드가 들어갑니다.
- `squares` 는 1 부터 4 까지의 제곱(1, 4, 9, 16)을 차례로 만드는 **제너레이터 표현식**입니다. 두 번째 빈칸에 표현식 전체를 한 줄로 적습니다.
- `print(type(squares))` 가 `<class 'generator'>` 를 출력해야 합니다. 리스트나 `iter(리스트)` 로 만들면 이 줄의 출력이 달라집니다.
- **빈칸만** 채웁니다. 다른 줄을 고치거나 줄을 추가하면 오답 처리됩니다.

## 출력 예

```
3
2
1
<class 'generator'>
1
4
9
16
```

