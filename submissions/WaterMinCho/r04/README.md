# 4회차 미니 모의고사

> 프로그램(`python study.py`)에서 풀면 이 폴더의 `quiz.py` 와 `.py` 파일에 답이 자동으로 저장됩니다.

문항 18개(보강할 단원 12개) · 평균 레벨 1.4 · 단원: s02 3, s21 3, s04 2, s06 2, s18 2, s07 1, s09 1, s10 1, s14 1, s16 1, s19 1

## s02_Q3 (프로그래밍 기초 · 객관식 · 2점)

다음 중 변수 이름으로 사용할 수 **없는** 것을 **모두** 고르세요.

1. `robot_2`
2. `2nd_robot`
3. `robot name`
4. `Robot`
5. `while`

## s02_Q4 (프로그래밍 기초 · 객관식 · 2점)

다음 코드에서 변수 `a`, `b`, `c` 의 자료형을 순서대로 바르게 적은 것은?

```python
a = 10.0
b = "True"
c = False
```

1. int, bool, bool
2. float, bool, bool
3. float, str, bool
4. float, str, str

## s02_Q10 (프로그래밍 기초 · 출력 예측 · 3점)

키보드로 `12` 와 `3` 을 차례로 입력했을 때, 다음 코드의 출력 결과를 그대로 적으세요.

```python
x = input()
y = input()
print(x + y)
print(int(x) + int(y))
```

## s09_Q11 (클래스(1) · 출력 예측 · 3점)

다음 코드의 출력 결과를 그대로 적으세요.

```python
class Basket:
    def __init__(self):
        self.items = []

    def put(self, x):
        self.items.append(x)

    def put_twice(self, x):
        self.put(x)
        self.put(x)

b1 = Basket()
b2 = Basket()
b1.put("egg")
b1.put_twice("milk")
b2.put_twice("tea")
print(b1.items)
print(len(b1.items), len(b2.items))
```

## s10_Q9 (클래스(2) · 출력 예측 · 3점)

다음 코드의 출력 결과를 그대로 적으세요.

```python
class Animal:
    legs = 4

    def eat(self):
        print("먹이를 먹는다")


class Bird(Animal):
    legs = 2

    def fly(self):
        print("날아간다")


b = Bird()
b.eat()
b.fly()
print(b.legs, Animal.legs)
```

## s14_Q4 (정규표현식 · 객관식 · 2점)

다음 두 패턴에 대한 설명으로 **옳은** 것은?

```python
import re
p1 = re.compile("a.c")
p2 = re.compile("a[.]c")
```

1. `p1.match("abc")` 는 매치되고, `p2.match("abc")` 는 매치되지 않는다.
2. `p1.match("a.c")` 는 매치되지 않는다.
3. `p2.match("a0c")` 는 매치된다.
4. `p1.match("ac")` 는 매치된다.

## s16_Q7 (알고리즘(1) · 출력 예측 · 3점)

다음 코드의 출력 결과를 그대로 적으세요.

```python
queue = []
queue.append("A")
queue.append("B")
first = queue.pop(0)
queue.append("C")
queue.append("D")
print(first)
print(queue)
print(queue.pop(0))
print(queue)
```

## s18_Q3 (Pandas·NumPy·Matplotlib · 객관식 · 2점)

다음 코드로 만든 두 Series 에 대한 설명으로 옳은 것은?

```python
import pandas as pd

s1 = pd.Series([10, 20, 30])
s2 = pd.Series({'a': 10, 'b': 20, 'c': 30})
```

1. `s1` 의 인덱스는 1, 2, 3 이다.
2. `s2` 의 인덱스는 0, 1, 2 이고, `a`, `b`, `c` 는 값으로 들어간다.
3. `s2` 의 인덱스는 `a`, `b`, `c` 이고, 값은 10, 20, 30 이다.
4. `s1` 과 `s2` 는 행과 열이 있는 2차원 테이블이다.

## s18_Q23 (Pandas·NumPy·Matplotlib · 객관식 · 2점)

다음 코드의 실행 결과는?

```python
import matplotlib.pyplot as plt

plt.plot([1, 2, 3], [4, 5, 6])
plt.xlabel('X-axis')
plt.ylabel('Y-axis')
plt.show()
```

1. 제목이 있는 선 그래프
2. x축과 y축 레이블이 있는 선 그래프
3. 점 그래프(산점도)
4. 에러 발생

## s19_Q8 (statsmodels·scikit-learn·SciPy · 단답 · 3점)

학습을 마친 선형 회귀 모델 `model` 의 결과를 요약한 표(OLS Regression Results)를 출력하려고 합니다. 빈칸(`____`)에 들어갈 메서드 이름을 적으세요.

```python
model = sm.OLS(y, X).fit()
print(model.____())
```

## s21_Q26 (파이썬 활용 심화(os·pathlib·JSON) · 객관식 · 2점)

API 에 대한 설명으로 옳지 **않은** 것은?

1. API 는 Application Programming Interface 의 줄임말이다.
2. API 는 프로그램 간에 데이터와 기능을 주고받을 수 있게 하는 인터페이스이다.
3. REST API 는 HTTP 프로토콜을 기반으로 JSON 형태의 데이터를 주고받는 방식이다.
4. REST API 로 받은 JSON 데이터는 파이썬 딕셔너리로 바꿀 수 없어 문자열 그대로 다뤄야 한다.

## s04_p01 (리스트와 딕셔너리 · 빈칸 채우기 · 동아리 명단 관리 · 4점)

파일: `s04_p01.py`

동아리 명단 리스트 `members` 를 아래 순서대로 고친 뒤 출력하는 프로그램입니다. 빈칸(`____`)을 채워 프로그램을 완성하세요.

1. 명단 맨 뒤에 `"하늘"` 을 추가합니다.
2. 1번 인덱스 자리에 `"도윤"` 을 끼워 넣습니다.
3. 0번 인덱스에 있는 요소를 삭제합니다.
4. 명단 전체와 2번 인덱스의 요소를 차례로 출력합니다.

빈칸만 채우세요. 다른 줄을 고치거나 줄을 추가하면 오답 처리됩니다.

## 시작 코드

```python
members = ["지호", "서연", "민재"]
members.____("하늘")
members.____(1, "도윤")
____ members[0]
print(members)
print(members[2])
```

## 출력 예

```
['도윤', '서연', '민재', '하늘']
민재
```

## s04_p02 (리스트와 딕셔너리 · 빈칸 채우기 · 장바구니 정리 · 4점)

파일: `s04_p02.py`

장바구니 리스트 `cart` 를 아래 순서대로 정리한 뒤 출력하는 프로그램입니다. 빈칸(`____`)을 채워 프로그램을 완성하세요.

1. `"우유"` 가 두 번 담겨 있습니다. 처음 나오는 `"우유"` 하나만 삭제합니다.
2. `"치즈"`, `"햄"` 두 개를 한꺼번에 맨 뒤에 추가합니다. 리스트 안에 리스트가 들어가면 안 됩니다.
3. 장바구니에 남아 있는 `"빵"` 을 `"식빵"` 으로 바꿉니다.
4. 장바구니 전체와 담긴 물건의 개수를 차례로 출력합니다.

빈칸만 채우세요. 다른 줄을 고치거나 줄을 추가하면 오답 처리됩니다.

## 시작 코드

```python
cart = ["우유", "빵", "우유", "계란"]
cart.____("우유")
cart.____(["치즈", "햄"])
cart[____] = "식빵"
print(cart)
print(len(cart))
```

## 출력 예

```
['식빵', '우유', '계란', '치즈', '햄']
5
```

## s06_p02 (함수(1) · 빈칸 채우기 · 상자 포장 · 4점)

파일: `s06_p02.py`

과자 `total` 개를 한 상자에 `size` 개씩 담으려고 합니다.
꽉 채운 상자의 수와 상자에 담지 못하고 남는 과자의 수를 한꺼번에 반환하는 `solution` 함수입니다.
빈칸(`____`)을 채워 함수를 완성하세요.

- **빈칸만** 채웁니다. 다른 줄을 고치거나 줄을 추가하면 오답 처리됩니다.
- 반환값은 `(꽉 채운 상자 수, 남는 과자 수)` 형태의 튜플이며, 두 값 모두 정수(int)여야 합니다.

## 주어진 코드

```python
def solution(total, size):
    boxes = ____
    rest = ____
    return boxes, rest
```

## 제한 사항
- 0 ≤ total ≤ 1000
- 1 ≤ size ≤ 100

## 입출력 예

| total | size | 반환값 |
|---|---|---|
| 17 | 5 | (3, 2) |
| 20 | 4 | (5, 0) |
| 3 | 10 | (0, 3) |

## s06_p04 (함수(1) · 출력 · 응원 구호 · 4점)

파일: `s06_p04.py`

다음 순서대로 프로그램을 작성하세요.

1. `ROKEY 화이팅!` 을 한 줄 출력하는 함수 `cheer` 를 정의합니다. (매개변수 없음)
2. 정수 `n` 을 입력받습니다.
3. `cheer` 함수를 `n` 번 호출합니다.

## 제한 사항
- 1 ≤ n ≤ 100

## 입출력 예

입력

```
3
```

출력

```
ROKEY 화이팅!
ROKEY 화이팅!
ROKEY 화이팅!
```

- 출력은 글자 하나까지 같아야 합니다(대소문자, 띄어쓰기, 느낌표 포함).

## s07_p05 (함수(2) · 반환값 · 누적 합계 · 6점)

파일: `s07_p05.py`

시작 코드의 첫 줄은 전역 변수 `total` 을 0 으로 만들어 둡니다.
`solution(num)` 을 호출할 때마다 **전역 변수 `total` 에 `num` 을 더하고, 더한 뒤의 `total` 값을 반환**하도록 함수를 완성하세요.

- 함수가 끝난 뒤에도 전역 변수 `total` 에 누적된 값이 남아 있어야 합니다.
- 함수 이름과 매개변수, 전역 변수 이름 `total` 은 바꾸지 않습니다.

## 제한 사항
- -1000 ≤ num ≤ 1000

## 입출력 예

프로그램을 새로 시작한 뒤(`total` 이 0 인 상태) 차례로 호출했을 때의 결과입니다.

| 순서 | 호출 | 반환값 | 호출 뒤 전역 변수 total |
|---|---|---|---|
| 1 | `solution(3)` | 3 | 3 |
| 2 | `solution(4)` | 7 | 7 |
| 3 | `solution(5)` | 12 | 12 |

- 채점은 `[solution(3), solution(4), solution(5)]` 처럼 연속으로 호출한 결과를 리스트로 모아 `[3, 7, 12]` 와 비교합니다.
- 호출이 끝난 뒤 전역 변수 `total` 의 값도 함께 확인합니다.
- 테스트마다 `total` 은 0 에서 다시 시작합니다.

## s21_p02 (파이썬 활용 심화(os·pathlib·JSON) · 반환값 · JSON 문자열에서 값 꺼내기 · 4점)

파일: `s21_p02.py`

JSON 객체가 적힌 문자열 `json_string` 과 키 `key` 가 주어집니다.
`json_string` 을 파이썬 딕셔너리로 바꾼 뒤, `key` 에 해당하는 값을 **반환(return)** 하는 `solution` 함수를 완성하세요.

- `key` 가 딕셔너리에 없으면 `None` 을 반환합니다.
- 값의 자료형은 변환된 그대로 돌려줍니다. JSON 의 숫자 `25` 는 정수 `25`, JSON 의 배열은 리스트입니다.
- 필요한 모듈은 직접 `import` 합니다.
- 함수 이름과 매개변수는 바꾸지 않습니다. `print` 가 아니라 `return` 으로 돌려줘야 합니다.

## 제한 사항
- `json_string` 은 올바른 JSON 객체(`{ ... }`)가 적힌 문자열이고, `key` 도 문자열입니다.

## 입출력 예

| json_string | key | 반환값 |
|---|---|---|
| `'{"name": "Alice", "age": 25, "city": "Seoul"}'` | `"name"` | `"Alice"` |
| `'{"name": "Alice", "age": 25, "city": "Seoul"}'` | `"age"` | `25` |
| `'{"name": "Alice", "age": 25, "city": "Seoul"}'` | `"job"` | `None` |
| `'{"skills": ["Python", "Django"], "level": 3}'` | `"skills"` | `["Python", "Django"]` |

## s21_p03 (파이썬 활용 심화(os·pathlib·JSON) · 출력 · 폴더 안의 항목 확인하기 · 4점)

파일: `s21_p03.py`

현재 폴더에 `sample_folder` 라는 폴더가 있습니다. 이름 하나를 입력받아, `os` 모듈로 `sample_folder` 안의 파일과 폴더 목록을 구한 뒤 아래 두 줄을 출력하는 프로그램을 작성하세요.

- 첫째 줄: `항목 수: N` (`N` 은 `sample_folder` 바로 안에 있는 파일과 폴더의 개수)
- 둘째 줄: 입력받은 이름이 목록에 있으면 `이름 있음`, 없으면 `이름 없음`
- 목록에는 `sample_folder` 바로 안에 있는 파일과 폴더의 이름만 들어 있습니다. 하위 폴더 안에 든 파일은 세지 않습니다.
- 목록의 순서는 운영 체제에 따라 달라질 수 있으므로 목록 자체는 출력하지 않습니다.
- 콜론(`:`) 뒤와 이름 뒤에 공백이 한 칸 있습니다.

## 입출력 예

`sample_folder` 안에 파일 `memo.txt`, `data.csv` 와 폴더 `images` 가 있고, `images` 폴더 안에 `cat.png` 가 있을 때

| 입력 | 출력 |
|---|---|
| `memo.txt` | `항목 수: 3`⏎`memo.txt 있음` |
| `report.txt` | `항목 수: 3`⏎`report.txt 없음` |
| `images` | `항목 수: 3`⏎`images 있음` |

첫 번째 예의 출력

```
항목 수: 3
memo.txt 있음
```

- 출력은 글자 하나까지 같아야 합니다(띄어쓰기 포함).

