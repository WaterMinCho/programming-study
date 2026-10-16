# 5회차 미니 모의고사

> 프로그램(`python study.py`)에서 풀면 이 폴더의 `quiz.py` 와 `.py` 파일에 답이 자동으로 저장됩니다.

문항 18개(보강할 단원 11개) · 평균 레벨 1.8 · 단원: s13 3, s01 2, s14 2, s15 2, s21 2, s03 1, s05 1, s08 1, s10 1, s11 1, s18 1, s19 1

## s01_Q25 (파이썬 소개 및 환경설정 · 객관식 · 2점)

VSCode 에서 아래 세 가지 일을 했습니다.

```
(가) [파일 → 폴더 열기] 로 작업 폴더를 연다.
(나) 확장(Extensions) 아이콘을 눌러 확장 검색 화면을 연다.
(다) print("hello VSCode") 를 입력한다.
```

(가), (나), (다)를 각각 화면의 어느 영역에서 하는지 순서대로 바르게 적은 것은?

1. 상단 메뉴 영역, 좌측 메뉴 영역, 텍스트 에디터 영역
2. 좌측 메뉴 영역, 상단 메뉴 영역, 텍스트 에디터 영역
3. 상단 메뉴 영역, 탐색기 영역, 하단 상태 표시 영역
4. 탐색기 영역, 좌측 메뉴 영역, 탐색기 영역

## s05_Q3 (반복문 · 객관식 · 2점)

다음 코드를 실행했더니 아래와 같이 출력되었습니다. 빈칸(`____`)에 들어갈 조건으로 알맞은 것은?

```python
count = 5
while ____:
    count -= 1
    print(count)
```

```
4
3
2
```

1. `count > 2`
2. `count >= 2`
3. `count > 3`
4. `count != 3`

## s10_Q20 (클래스(2) · 출력 예측 · 3점)

다음 코드의 출력 결과를 그대로 적으세요.

```python
class Battery:
    def __init__(self, name, level):
        self.name = name
        self.level = level

    def info(self):
        print(self.name, self.level)


class SolarBattery(Battery):
    def charge(self):
        self.level = self.level + self.level // 4
        print("충전 완료")


s = SolarBattery("태양광", 40)
s.charge()
s.info()
b = Battery("일반", 40)
b.info()
```

## s11_Q28 (GUI 프로그래밍(PyQt6 · tkinter) · 단답 · 3점)

`QComboBox` 의 선택 항목이 바뀔 때마다 바뀐 항목의 문자열이 라벨에 표시되게 하려 합니다. `combo.____.connect(label.setText)` 의 빈칸에 들어갈 시그널의 이름을 적으세요.

## s13_Q7 (예외 처리·문자열·람다·map · 객관식 · 2점)

실행했을 때 `[2, 4, 6]` 이 출력되는 코드는?

1. `print(map(lambda x: x * 2, [1, 2, 3]))`
2. `print(list(map(lambda x: x * 2, [1, 2, 3])))`
3. `print(list(map(lambda x: x + 2, [1, 2, 3])))`
4. `print(lambda x: x * 2, [1, 2, 3])`

## s13_Q11 (예외 처리·문자열·람다·map · 출력 예측 · 3점)

다음 코드의 출력 결과를 그대로 적으세요.

```python
def divide(a, b):
    try:
        print("계산 시작")
        result = a / b
        print("결과:", result)
    except ZeroDivisionError:
        print("0으로 나눌 수 없습니다")
    finally:
        print("계산 종료")

divide(10, 4)
divide(3, 0)
```

## s13_Q18 (예외 처리·문자열·람다·map · 출력 예측 · 3점)

다음 코드의 출력 결과를 그대로 적으세요.

```python
def withdraw(balance, amount):
    if amount > balance:
        raise ValueError("잔액 부족")
    print("출금 완료")
    return balance - amount

try:
    left = withdraw(5000, 3000)
    print("남은 돈:", left)
    left = withdraw(left, 4000)
    print("남은 돈:", left)
except ValueError as e:
    print("실패:", e)
print("끝")
```

## s14_Q10 (정규표현식 · 출력 예측 · 3점)

다음 코드의 출력 결과를 그대로 적으세요.

```python
import re
p = re.compile("[a-z]+", re.I)
m = p.match("Hello World")
print(m)
print(m.group())
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

## s19_Q19 (statsmodels·scikit-learn·SciPy · 객관식 · 2점)

다음은 그룹 A 의 점수에 대한 기본 통계를 계산하는 프로그램입니다. 출력되는 결과에 대한 설명으로 옳지 **않은** 것은?

```python
from scipy.stats import describe

group_a = [80, 85, 90, 75, 95]
stats = describe(group_a)
print(stats)
```

1. `nobs` 는 데이터의 개수인 5 이다.
2. `minmax` 는 최솟값과 최댓값을 묶은 (75, 95) 이다.
3. `mean` 은 평균인 85.0 이다.
4. `median` 은 중앙값인 85 이다.

## s21_Q18 (파이썬 활용 심화(os·pathlib·JSON) · 객관식 · 2점)

pandas 로 Excel 파일을 읽어 만든 DataFrame `df` 가 있습니다. 수치형 데이터의 평균, 최댓값, 최솟값 같은 요약 정보를 보여 주는 코드는?

1. `df.head()`
2. `df.info()`
3. `df.to_excel()`
4. `df.describe()`

## s01_p04 (파이썬 소개 및 환경설정 · 출력 · 오류 고치기 · 6점)

파일: `s01_p04.py`

파이썬 개발 도구 이름 세 개를 한 줄에 하나씩 출력하려고 만든 프로그램입니다.
그런데 **잘못된 곳이 세 군데** 있어서 원하는 대로 출력되지 않습니다.
시작 코드를 고쳐서 아래 **출력 예**와 똑같이 출력되게 하세요.

## 시작 코드

```python
Print("IDLE")
print("Colab")
print(VSCode)
```

## 출력 예

```
IDLE
VSCode
Colab
```

- 출력은 글자 하나까지 같아야 합니다(대소문자 포함). 줄의 순서도 예시와 같아야 합니다.
- 실행해 보지 않고, 어느 줄에서 어떤 오류가 날지 먼저 눈으로 찾아보세요.

## s03_p07 (조건식과 제어문 · 출력 · 간단 계산기 · 6점)

파일: `s03_p07.py`

정수 두 개와 연산 기호를 입력받아 계산 결과를 출력하는 프로그램을 작성하세요.

## 입력
- 첫째 줄: 정수 `a`
- 둘째 줄: 연산 기호(문자열)
- 셋째 줄: 정수 `b`

## 출력
- 연산 기호가 `+`, `-`, `*`, `/` 중 하나이면 `a 기호 b = 결과` 형식으로 출력합니다. 각 항목 사이는 **공백 한 칸**입니다.
  - `+` 는 덧셈, `-` 는 뺄셈, `*` 는 곱셈, `/` 는 나눗셈(파이썬의 `/` 연산 결과 그대로)입니다.
- 그 밖의 기호가 입력되면 `지원하지 않는 연산자입니다.` 를 출력합니다.

## 제한 사항
- -1000 ≤ a, b ≤ 1000
- 연산 기호가 `/` 일 때 b 는 0 이 아닙니다.

## 입력 예 1

```
7
+
3
```

## 출력 예 1

```
7 + 3 = 10
```

## 입력 예 2

```
8
/
2
```

## 출력 예 2

```
8 / 2 = 4.0
```

## 입력 예 3

```
5
%
2
```

## 출력 예 3

```
지원하지 않는 연산자입니다.
```

## s08_p11 (자료구조와 알고리즘 · 빈칸 채우기 · 큰 값부터 놓는 선택 정렬 · 6점)

파일: `s08_p11.py`

숫자 리스트 `nums` 를 큰 값부터 작은 값 순서(내림차순)로 정렬해 반환하는 함수 `sort_desc` 입니다.

- 바깥쪽 반복(`i`)의 한 단계마다, 인덱스 `i` 부터 끝까지의 요소 중 가장 큰 값의 위치를 `pos` 에 기억합니다.
- 안쪽 반복이 끝나면 `nums[i]` 와 `nums[pos]` 를 한 줄로 맞바꿉니다.

빈칸(`____`) 두 곳을 채워 함수를 완성하세요.

- **빈칸만** 채웁니다. 다른 줄을 고치거나 줄을 추가하면 오답 처리됩니다.

## 시작 코드

```python
def sort_desc(nums):
    for i in range(0, len(nums) - 1, 1):
        pos = i
        for j in range(i + 1, len(nums), 1):
            if ____:
                pos = j
        nums[i], nums[pos] = ____
    return nums
```

## 입출력 예

| 호출 | 반환값 |
|---|---|
| `sort_desc([3, 8, 5])` | `[8, 5, 3]` |
| `sort_desc([30, 10, 40, 20, 15])` | `[40, 30, 20, 15, 10]` |
| `sort_desc([-2, -7, 0])` | `[0, -2, -7]` |

## s14_p10 (정규표현식 · 빈칸 채우기 · 해시태그 뽑기 · 6점)

파일: `s14_p10.py`

한 줄을 입력받아, `#` 뒤에 영문자·숫자·밑줄(`_`)이 1개 이상 이어진 해시태그를 모두 찾아
개수를 먼저 출력하고, 이어서 해시태그를 나온 순서대로 한 줄에 하나씩 출력하는 프로그램입니다.
빈칸(`____`) 1곳을 채워 프로그램을 완성하세요.

```python
import re

text = input()
tags = re.findall(____, text)   # '#' 뒤에 글자·숫자·밑줄이 1개 이상 이어진 덩어리
print(len(tags))
for t in tags:
    print(t)
```

- 빈칸에는 정규식 패턴 문자열이 들어갑니다. 역슬래시를 쓰려면 `r"..."` 로 적는 것이 안전합니다.
- `#` 바로 뒤에 글자가 없으면(`# empty`) 해시태그가 아닙니다. 하이픈 등 다른 글자가 나오면 그 앞까지만 태그입니다(`#x-y` → `#x`).
- 해시태그가 하나도 없으면 `0` 만 출력합니다.
- **빈칸만** 채웁니다. 다른 줄을 고치거나 줄을 추가하면 오답 처리됩니다.

## 입출력 예

입력
```
#python #re_study 2024 #day1
```
출력
```
3
#python
#re_study
#day1
```

입력
```
# empty #a#b
```
출력
```
2
#a
#b
```

## s15_p10 (고급 함수 · 빈칸 채우기 · 거꾸로 꺼내는 이터레이터 클래스 · 6점)

파일: `s15_p10.py`

전달받은 데이터(리스트나 문자열)의 원소를 **맨 뒤에서부터** 하나씩 돌려주는 이터레이터 클래스 `Rewinder` 입니다.
빈칸(`____`) 2곳을 채워 클래스를 완성하세요.

```python
class Rewinder:
    def __init__(self, data):
        self.data = data
        self.pos = ____

    def __iter__(self):
        return self

    def __next__(self):
        if ____:
            raise StopIteration
        item = self.data[self.pos]
        self.pos = self.pos - 1
        return item
```

- 첫 번째 빈칸에는 처음 꺼낼 원소(마지막 원소)의 인덱스를 구하는 식이 들어갑니다.
- 두 번째 빈칸에는 맨 앞 원소까지 돌려준 뒤에 참이 되는 조건이 들어갑니다. 맨 앞 원소(인덱스 0)는 빠지지 않고 나와야 합니다.
- `data` 가 비어 있으면 아무 값도 돌려주지 않습니다.
- **빈칸만** 채웁니다. 다른 줄을 고치거나 줄을 추가하면 오답 처리됩니다.

## 테스트 코드와 출력 예

```python
for x in Rewinder([1, 2, 3]):
    print(x)
```

```
3
2
1
```

```python
print(list(Rewinder("abc")))
print(list(Rewinder([])))
```

```
['c', 'b', 'a']
[]
```

```python
r = Rewinder([7])
print(next(r))
try:
    next(r)
except StopIteration:
    print("stop")
```

```
7
stop
```

## s15_p15 (고급 함수 · 반환값 · 짝수의 제곱 이터레이터 · 6점)

파일: `s15_p15.py`

정수 `n` 이 주어질 때, 0 부터 `n` 까지의 정수 가운데 짝수만 골라 그 제곱을 작은 수부터 하나씩 돌려주는 **이터레이터**를 반환(return)하는 `solution` 함수를 완성하세요.

예를 들어 `n` 이 6 이면 0, 2, 4, 6 의 제곱인 0, 4, 16, 36 을 차례로 돌려줍니다.

- 반환값은 리스트가 아니라 `next()` 에 바로 넣을 수 있는 이터레이터여야 합니다. `iter()` 로 바꾼 것, 제너레이터 표현식, `yield` 를 쓴 제너레이터 가운데 어느 것으로 만들어도 됩니다.
- `n` 도 범위에 들어갑니다. 0 은 짝수입니다.
- 채점은 `next(solution(...))`, `sum(solution(...))`, `list(solution(...))` 으로 확인합니다.

## 제한 사항
- 0 ≤ n ≤ 1000

## 입출력 예

| 호출 | 결과 |
|---|---|
| `next(solution(9))` | `0` |
| `sum(solution(4))` | `20` |
| `list(solution(6))` | `[0, 4, 16, 36]` |
| `list(solution(0))` | `[0]` |

## s21_p01 (파이썬 활용 심화(os·pathlib·JSON) · 빈칸 채우기 · JSON 파일로 저장하고 불러오기 · 4점)

파일: `s21_p01.py`

딕셔너리 `data` 를 `data.json` 파일로 저장한 다음, 그 파일을 다시 읽어 딕셔너리로 불러오는 프로그램입니다.
빈칸(`____`) 3곳을 채워 프로그램을 완성하세요.

- 첫 번째 빈칸: 파이썬 객체를 JSON 형식으로 **파일에** 저장하는 `json` 모듈의 함수
- 두 번째 빈칸: 그 함수에 넘겨 줄, 저장할 파일 객체
- 세 번째 빈칸: JSON **파일을** 읽어 파이썬 객체로 돌려주는 `json` 모듈의 함수
- 빈칸만 채웁니다. 다른 줄을 고치거나 줄을 추가하면 오답 처리됩니다.

```python
import json

data = {"name": "홍길동", "age": 25, "city": "서울"}

with open("data.json", "w", encoding="utf-8") as file:
    json.____(data, ____, indent=4)

with open("data.json", "r", encoding="utf-8") as file:
    loaded = json.____(file)

print(loaded["name"], loaded["age"], loaded["city"])
print(type(loaded))
print(loaded == data)
```

## 출력 예

```
홍길동 25 서울
<class 'dict'>
True
```

`data.json` 에 다른 내용이 이미 적혀 있는 상태에서 실행해도 출력은 위와 같아야 합니다.

