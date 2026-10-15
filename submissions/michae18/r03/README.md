# 3회차 미니 모의고사

> 프로그램(`python study.py`)에서 풀면 이 폴더의 `quiz.py` 와 `.py` 파일에 답이 자동으로 저장됩니다.

문항 18개(보강할 단원 21개) · 평균 레벨 1.7 · 단원: s02 2, s04 2, s07 2, s09 2, s14 2, s03 1, s10 1, s11 1, s16 1, s17 1, s18 1, s20 1, s21 1

## s02_Q17 (프로그래밍 기초 · 객관식 · 2점)

다음 코드에 대한 설명으로 옳지 **않은** 것은?

```python
price = 1200
total = price * 3
```

1. 첫째 줄에서 대입 연산자 왼쪽의 `price` 는 l_value, 오른쪽의 `1200` 은 r_value 이다.
2. 둘째 줄의 `price` 는 대입 연산자 오른쪽에 있으므로 저장된 값 `1200` 으로 해석된다.
3. 둘째 줄은 `price * 3` 을 먼저 계산한 뒤 그 결과를 `total` 에 저장한다.
4. 둘째 줄을 실행하고 나면 `price` 에 저장된 값도 `3600` 으로 바뀐다.
5. 둘째 줄을 실행하고 나면 `total` 은 정수형 변수이다.

## s04_Q6 (리스트와 딕셔너리 · 객관식 · 2점)

`user` 딕셔너리에 없는 키 `'email'` 로 값을 꺼내려고 합니다. ①과 ②를 **각각 따로** 실행했을 때의 결과로 옳은 것은?

```python
user = {'id': 'rokey', 'level': 3}
print(user.get('email'))   # ①
print(user['email'])       # ②
```

1. ①은 `None` 이 출력되고, ②는 오류가 발생한다
2. ①은 오류가 발생하고, ②는 `None` 이 출력된다
3. ①과 ② 모두 `None` 이 출력된다
4. ①과 ② 모두 오류가 발생한다

## s04_Q16 (리스트와 딕셔너리 · 출력 예측 · 3점)

다음 코드의 출력 결과를 그대로 적으세요.

```python
scores = [70, 85, 70, 95]
print(len(scores))
print(sum(scores))
print(sum(scores) / len(scores))
```

## s07_Q8 (함수(2) · 출력 예측 · 3점)

다음 코드의 출력 결과를 그대로 적으세요.

```python
def swap(pa, pb):
    temp = pa
    pa = pb
    pb = temp
    print("함수 안:", pa, pb)

na = 3
nb = 8
swap(na, nb)
print("함수 밖:", na, nb)
na, nb = nb, na
print("교환 후:", na, nb)
```

## s09_Q10 (클래스(1) · 출력 예측 · 3점)

다음 코드의 출력 결과를 그대로 적으세요.

```python
class Lamp:
    def __init__(self):
        print("lamp ready")
        self.on = False

    def switch(self):
        self.on = not self.on
        print("on:", self.on)

print("start")
a = Lamp()
a.switch()
a.switch()
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

## s10_Q21 (클래스(2) · 출력 예측 · 3점)

다음 코드의 출력 결과를 그대로 적으세요. (`pass` 는 아무 일도 하지 않는 자리 채움 문장입니다)

```python
class Staff:
    def __init__(self, name):
        self.name = name

    def pay(self):
        return 100


class Driver(Staff):
    def pay(self):
        return 150


class Intern(Staff):
    pass


team = [Driver("Kim"), Intern("Lee"), Staff("Park")]
total = 0
for member in team:
    print(member.name, member.pay())
    total = total + member.pay()
print(total)
```

## s14_Q29 (정규표현식 · 객관식 · 2점)

다음 코드의 출력 결과는?

```python
import re
p = re.compile("^python\s\w+")

data = """python one
life is too short
python two
you need python
python three"""

print(p.findall(data))
```

1. `['python one']`
2. `['python one', 'python two', 'python three']`
3. `['python one', 'python two', 'you need python', 'python three']`
4. `[]`

## s17_Q22 (알고리즘(2) · 객관식 · 2점)

DFS 와 BFS 의 영어 이름과 우리말 이름을 옳게 짝지은 것은?

1. DFS 는 Depth First Search(너비 우선 탐색), BFS 는 Breadth First Search(깊이 우선 탐색)
2. DFS 는 Data First Search(깊이 우선 탐색), BFS 는 Binary First Search(너비 우선 탐색)
3. DFS 는 Depth First Search(깊이 우선 탐색), BFS 는 Breadth First Search(너비 우선 탐색)
4. DFS 는 Down First Search(깊이 우선 탐색), BFS 는 Bottom First Search(너비 우선 탐색)

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

## s20_Q1 (Seaborn·OpenCV · 객관식 · 2점)

다음 코드가 오류 없이 실행되도록 빈칸에 들어갈 import 문은?

```python
____
import matplotlib.pyplot as plt

iris = sns.load_dataset("iris")
sns.scatterplot(data=iris, x="sepal_length", y="sepal_width")
plt.show()
```

1. `import seaborn as sn`
2. `import seaborn as sb`
3. `import seaborn as sns`
4. `import seaborn as seaborn`

## s02_p06 (프로그래밍 기초 · 출력 · 사칙연산 계산기 · 6점)

파일: `s02_p06.py`

정수 두 개를 한 줄에 하나씩 입력받아, 두 수의 덧셈·뺄셈·곱셈·나눗셈 결과를 아래 형식으로 한 줄씩 출력하는 프로그램을 작성하세요.

- 첫째 줄에 첫 번째 정수, 둘째 줄에 두 번째 정수가 입력됩니다.
- 두 번째 정수로 0 은 입력되지 않습니다.
- 나눗셈은 `/` 연산자의 결과를 그대로 출력합니다(예: `20 / 5` 의 결과는 `4.0`).

## 입출력 예

입력

```
20
5
```

출력

```
20 + 5 = 25
20 - 5 = 15
20 * 5 = 100
20 / 5 = 4.0
```

입력

```
7
2
```

출력

```
7 + 2 = 9
7 - 2 = 5
7 * 2 = 14
7 / 2 = 3.5
```

- 숫자와 기호(`+`, `-`, `*`, `/`, `=`) 사이에는 공백이 한 칸씩 있습니다.
- 덧셈, 뺄셈, 곱셈, 나눗셈 순서로 한 줄씩 출력합니다.

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

## s11_p07 (GUI 프로그래밍(PyQt6 · tkinter) · 반환값 · 입력창 수량 검사 · 6점)

파일: `s11_p07.py`

수량을 적는 입력창(`QLineEdit`)과 `확인` 버튼이 있는 주문 창에서, 버튼을 눌렀을 때 입력창의 글자를 검사해 라벨에 표시할 문장을 만드는 슬롯 함수의 핵심 부분입니다. `entry.text()` 가 돌려준 문자열 `text` 를 받아 결과 문자열을 반환하는 `solution` 함수를 완성하세요.

- `text` 가 비어 있지 않고, 모든 글자가 `0`~`9` 숫자이며, 정수로 바꾼 값이 1 이상 99 이하이면 `"수량: N개"` 를 반환합니다. `N` 은 정수로 바꾼 값입니다(`"007"` 은 `7`).
- 그 밖의 경우(빈 문자열, 숫자가 아닌 글자가 하나라도 있음, 0 이하이거나 100 이상)는 `"1~99 사이의 숫자를 입력하세요."` 를 반환합니다.
- 공백도 숫자가 아닌 글자로 취급합니다. 입력창의 글자를 다듬지 않고 그대로 검사합니다.
- 함수 이름과 매개변수는 바꾸지 않습니다. `print` 가 아니라 `return` 으로 돌려줍니다.

## 제한 사항
- `text` 의 길이는 0 이상 10 이하

## 입출력 예

| text | 반환값 |
|---|---|
| `"3"` | `"수량: 3개"` |
| `"99"` | `"수량: 99개"` |
| `"100"` | `"1~99 사이의 숫자를 입력하세요."` |
| `"0"` | `"1~99 사이의 숫자를 입력하세요."` |
| `""` | `"1~99 사이의 숫자를 입력하세요."` |
| `"3.5"` | `"1~99 사이의 숫자를 입력하세요."` |
| `"007"` | `"수량: 7개"` |

## s14_p19 (정규표현식 · 출력 · 이메일 형식 검사 · 6점)

파일: `s14_p19.py`

이메일 주소 후보를 한 줄 입력받아, 아래 형식에 맞으면 `Valid email`, 맞지 않으면 `Invalid email` 을
출력하는 프로그램을 작성하세요.

이 문제에서 올바른 이메일 형식은 `아이디@도메인` 모양이고(예: `user@example.com`), 입력된 문자열 **전체**가 이 모양이어야 합니다.

- 아이디는 영문자·숫자·밑줄(`_`)·점(`.`)·하이픈(`-`)이 1개 이상 이어진 것입니다.
- 도메인은 아이디와 같은 종류의 글자가 1개 이상 이어진 뒤, 점(`.`) 하나와 영문자·숫자·밑줄 1개 이상으로 끝납니다. `example.com` 과 `mail.rokey.co.kr` 은 도메인으로 인정되고, 점이 없는 `example` 은 인정되지 않습니다.
- 주소의 앞이나 뒤에 다른 글자가 붙어 있으면 올바른 형식이 아닙니다(`to user@example.com`, `user@example.com!!`).
- 입력은 영문자, 숫자, 공백, 문장부호로만 이루어지고, 빈 줄일 수도 있습니다.

## 입출력 예

입력

```
user@example.com
```

출력

```
Valid email
```

입력

```
user@example
```

출력

```
Invalid email
```

입력

```
user@example.com!!
```

출력

```
Invalid email
```

- 출력은 글자 하나까지 같아야 합니다(대소문자, 띄어쓰기 포함).

## s16_p06 (알고리즘(1) · 반환값 · 괄호 짝 검사 · 6점)

파일: `s16_p06.py`

문자열 `s` 가 주어집니다. `s` 에 들어 있는 소괄호 `(` 와 `)` 의 짝이 올바르게 맞으면 `True`, 아니면 `False` 를 반환하는 `solution` 함수를 스택을 이용해 완성하세요.

- 괄호가 아닌 문자(영문자, 숫자, 연산 기호 등)는 무시합니다.
- 짝이 맞는다는 것은, 모든 `)` 가 그보다 앞에 나온 아직 닫히지 않은 `(` 와 하나씩 짝을 이루고, 끝났을 때 닫히지 않은 `(` 가 남지 않는 것입니다.
- 괄호가 하나도 없는 문자열(빈 문자열 포함)은 `True` 입니다.
- 함수 이름과 매개변수는 바꾸지 않습니다. `print` 가 아니라 `return` 으로 돌려줍니다.

## 제한 사항
- `s` 의 길이는 0 이상 100 이하

## 입출력 예

| s | 반환값 |
|---|---|
| `"()"` | `True` |
| `"(())"` | `True` |
| `"(()"` | `False` |
| `"())"` | `False` |
| `")("` | `False` |
| `"(a+b)*(c-d)"` | `True` |
| `""` | `True` |

힌트: `(` 를 만나면 push, `)` 를 만나면 pop. pop 할 것이 없거나, 다 보고도 스택에 남아 있으면 `False`.

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

