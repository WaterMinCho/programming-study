# 4회차 미니 모의고사

> 프로그램(`python study.py`)에서 풀면 이 폴더의 `quiz.py` 와 `.py` 파일에 답이 자동으로 저장됩니다.

문항 18개(보강할 단원 15개 · 직전 득점률이 높아 조금 더) · 평균 레벨 1.4 · 단원: s11 3, s05 2, s16 2, s19 2, s21 2, s03 1, s04 1, s06 1, s07 1, s14 1, s17 1, s20 1

## s03_Q7 (조건식과 제어문 · 객관식 · 2점)

제어문과 조건문에 대한 설명으로 **옳지 않은** 것은?

1. 프로그램은 기본적으로 위에서 아래로 차례대로 실행되고, 제어문은 이 흐름을 바꾼다.
2. 제어문에는 조건문과 반복문이 있다.
3. `else` 뒤에도 `elif` 처럼 조건식을 적어야 한다.
4. `elif` 와 `else` 는 `if` 없이 단독으로 쓸 수 없다.

## s05_Q16 (반복문 · 출력 예측 · 3점)

다음 코드의 출력 결과를 그대로 적으세요.

```python
for n in range(0, 31, 5):
    if n % 3 == 0:
        print(n, end=" ")
print("끝")
```

## s07_Q10 (함수(2) · 출력 예측 · 3점)

다음 코드의 출력 결과를 그대로 적으세요. (띄어쓰기까지 정확히)

```python
def room(width=6, height=2):
    print("width=", width, "height=", height)

room()
room(9)
room(9, 5)
```

## s11_Q9 (GUI 프로그래밍(PyQt6 · tkinter) · 객관식 · 2점)

`move()` 를 이용한 절대 좌표 배치에 대한 설명으로 옳지 **않은** 것은?

1. 레이아웃 관리자 없이 `btn.move(10, 60)` 처럼 x, y 픽셀 위치를 직접 지정한다.
2. `QPushButton("PUSH", window)` 처럼 위젯을 만들 때 부모 창을 넘겨 주어야 그 창 안에 나타난다.
3. 창 크기가 바뀌면 위젯의 위치도 자동으로 다시 계산된다.
4. 창 크기 변경에 반응하지 않아 레이아웃 관리자보다 사용률이 낮다.

## s11_Q30 (GUI 프로그래밍(PyQt6 · tkinter) · 단답 · 3점)

tkinter 에서 여러 항목 가운데 하나만 고르게 할 때 쓰는 위젯의 클래스 이름을 적으세요. 같은 `variable` 을 넘겨 만든 것들 가운데 하나만 선택되고, 선택하면 그 위젯의 `value` 가 `variable` 에 저장됩니다. (`tk.____(root, text="포장", variable=choice, value=1)` 의 빈칸. 대소문자까지 정확히 적습니다)

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

## s16_Q9 (알고리즘(1) · 출력 예측 · 3점)

다음 코드의 출력 결과를 그대로 적으세요.

```python
class Stack:
    def __init__(self):
        self.stack = []

    def push(self, data):
        self.stack.append(data)

    def pop(self):
        if not self.is_empty():
            return self.stack.pop()
        return

    def is_empty(self):
        if len(self.stack) == 0:
            return True
        return False

    def peak(self):
        if not self.is_empty():
            return self.stack[-1]
        return

s = Stack()
print(s.pop())
s.push(5)
s.push(7)
print(s.peak())
s.pop()
s.push(9)
print(s.peak(), s.is_empty())
print(s.stack)
```

## s17_Q8 (알고리즘(2) · 출력 예측 · 3점)

다음 코드의 출력 결과를 그대로 적으세요.

```python
graph = [[0, 1, 1], [0, 0, 1], [1, 0, 0], [1, 1, 0]]
print(len(graph), len(graph[0]))
print(graph[1][2], graph[2][1])
for row in graph:
    print(row)
```

## s19_Q2 (statsmodels·scikit-learn·SciPy · 객관식 · 2점)

statsmodels 에서 독립 변수에 상수항(절편)을 추가하는 함수는?

1. `sm.add_constant()`
2. `sm.add_intercept()`
3. `sm.include_constant()`
4. `sm.set_constant()`

## s19_Q9 (statsmodels·scikit-learn·SciPy · 객관식 · 2점)

세 패키지에 대한 설명으로 옳지 **않은** 것은?

1. statsmodels 는 선형 회귀와 로지스틱 회귀 분석, ARIMA 모델을 포함한 시계열 분석, 가설 검정 같은 통계적 테스트 기능을 제공하고, 강의에서는 `import statsmodels.api as sm` 으로 불러왔다.
2. scikit-learn 은 파이썬 기반의 머신러닝 라이브러리이고, `pip install scikit-learn` 으로 설치한 뒤 `import scikit-learn as sk` 로 불러온다.
3. scikit-learn 의 모델은 종류가 달라도 `fit(X, y)`, `predict(X)`, `score(X, y)` 같은 공통 메서드를 쓴다.
4. SciPy 는 과학 및 공학 계산 라이브러리이고 NumPy 위에 구축되어 있다.

## s20_Q2 (Seaborn·OpenCV · 객관식 · 2점)

Seaborn 과 OpenCV 에 대한 설명으로 옳지 **않은** 것은?

1. Seaborn 은 통계 그래프를 짧은 코드로 그리는 파이썬 데이터 시각화 라이브러리이다.
2. Seaborn 은 Matplotlib 위에서 동작하므로 `plt.title()`, `plt.show()` 와 함께 쓴다.
3. OpenCV 는 실시간 컴퓨터 비전을 위한 라이브러리로, 이미지와 영상을 처리하는 기능을 제공한다.
4. OpenCV 는 `pip install opencv-python` 으로 설치하고 `import opencv` 로 불러온다.

## s04_p09 (리스트와 딕셔너리 · 출력 · 회원 정보 추가 · 6점)

파일: `s04_p09.py`

회원 정보를 담은 딕셔너리 `member` 가 시작 코드에 주어져 있습니다.
키를 첫째 줄에, 값을 둘째 줄에 입력받아 `member` 에 저장한 다음, 첫째 줄에 `member` 의 모든 키를, 둘째 줄에 모든 값을 출력하는 프로그램을 작성하세요.

- 입력받은 키와 값은 문자열 그대로 저장합니다.
- 입력한 키가 이미 `member` 에 있으면 그 키의 값이 새 값으로 바뀝니다.
- 모든 키는 `keys()`, 모든 값은 `values()` 메서드의 결과를 그대로 `print` 합니다.

## 입출력 예 1

입력

```
지역
판교
```

출력

```
dict_keys(['이름', '기수', '트랙', '지역'])
dict_values(['지우', 11, '로봇', '판교'])
```

## 입출력 예 2

입력

```
트랙
AI
```

출력

```
dict_keys(['이름', '기수', '트랙'])
dict_values(['지우', 11, 'AI'])
```

## s05_p12 (반복문 · 빈칸 채우기 · for 를 while 로 바꾸기 · 6점)

파일: `s05_p12.py`

아래 프로그램은 세 정수 `start`, `end`, `step` 을 입력받아 `start` 부터 `end` 까지(끝 포함) `step` 씩 커지는 수를
한 줄에 하나씩 출력합니다.

```python
start = int(input())
end = int(input())
step = int(input())
for num in range(start, end + 1, step):
    print(num)
```

이 프로그램의 `for` 문을 `while` 문으로 바꿔 쓴 것이 아래 시작 코드입니다. 어떤 입력에도 위 프로그램과 같은 출력이 나오도록
빈칸(`____`) 세 곳을 채워 프로그램을 완성하세요.

- 빈칸만 채웁니다. 다른 줄을 고치거나 줄을 추가하면 오답 처리됩니다.

## 시작 코드

```python
start = int(input())
end = int(input())
step = int(input())
num = ____
while ____:
    print(num)
    ____
```

## 제한 사항
- 1 ≤ start ≤ end ≤ 100
- 1 ≤ step ≤ 10

## 입출력 예

입력

```
2
11
3
```

출력

```
2
5
8
11
```

입력

```
1
10
4
```

출력

```
1
5
9
```

## s06_p05 (함수(1) · 빈칸 채우기 · 날씨 판별 · 6점)

파일: `s06_p05.py`

기온(정수)을 입력받아 날씨를 판별해 출력하는 프로그램입니다.
`weather` 함수는 기온에 따라 다음 문자열을 반환합니다.

| 기온 | 반환값 |
|---|---|
| 28 이상 | `"hot"` |
| 5 이하 | `"cold"` |
| 그 밖 | `"mild"` |

빈칸(`____`)을 채워 프로그램을 완성하세요.

- **빈칸만** 채웁니다. 다른 줄을 고치거나 줄을 추가하면 오답 처리됩니다.

## 주어진 코드

```python
def weather(temp):
    if temp >= 28:
        ____ "hot"
    elif temp <= 5:
        ____ "cold"
    return "mild"

t = int(input())
result = ____
print(t, "->", result)
```

## 제한 사항
- -50 ≤ 기온 ≤ 50

## 입출력 예

| 입력 | 출력 |
|---|---|
| `30` | `30 -> hot` |
| `5` | `5 -> cold` |
| `17` | `17 -> mild` |

## s11_p01 (GUI 프로그래밍(PyQt6 · tkinter) · 빈칸 채우기 · 버튼 클릭 연결 흉내 · 4점)

파일: `s11_p01.py`

PyQt6 의 `btn.clicked.connect(order)` 가 하는 일을 GUI 없이 흉내 낸 프로그램입니다. 빈칸(`____`) 2곳을 채워 완성하세요.

- `Button` 클래스의 `connect(func)` 는 전달받은 함수를 `self.slot` 에 저장만 합니다.
- `click()` 은 저장해 둔 함수를 호출합니다. 버튼이 클릭된 상황에 해당합니다.
- 프로그램은 클릭 횟수를 한 줄 입력받아, 그 횟수만큼 `click()` 을 호출합니다. 클릭할 때마다 `order` 함수가 실행되어 `주문하세요` 가 한 줄씩 출력되어야 합니다.
- 빈칸만 채웁니다. 다른 줄을 고치거나 줄을 추가하면 오답 처리됩니다.

```python
def order():
    print("주문하세요")


class Button:
    def connect(self, func):
        self.slot = func

    def click(self):
        self.____()


btn = Button()
btn.connect(____)
clicks = int(input())
for i in range(clicks):
    btn.click()
```

## 입출력 예

| 입력 | 출력 |
|---|---|
| `3` | `주문하세요`<br>`주문하세요`<br>`주문하세요` |
| `1` | `주문하세요` |
| `0` | (아무것도 출력하지 않음) |

## s16_p15 (알고리즘(1) · 출력 · 비어 있으면 -1 을 돌려주는 큐 · 6점)

파일: `s16_p15.py`

리스트를 이용해 큐를 구현한 `Queue` 클래스를 정의하세요.

| 구분 | 이름 | 내용 |
|---|---|---|
| 생성자 | `__init__()` | 빈 리스트를 인스턴스 변수 `queue` 로 만듭니다 |
| 메서드 | `enqueue(x)` | `x` 를 큐의 맨 뒤에 넣습니다 |
| 메서드 | `dequeue()` | 큐의 맨 앞 값을 제거하고 반환합니다. 큐가 비어 있으면 정수 `-1` 을 반환합니다 |
| 메서드 | `front()` | 큐의 맨 앞 값을 제거하지 않고 반환합니다. 큐가 비어 있으면 정수 `-1` 을 반환합니다 |
| 메서드 | `is_empty()` | 큐가 비어 있으면 `True`, 아니면 `False` 를 반환합니다 |

- 클래스만 정의하면 됩니다. 채점할 때는 아래와 같은 테스트 코드가 객체를 만들어 메서드를 호출합니다.
- 메서드는 값을 출력하지 않고 반환합니다.
- 리스트의 앞이 큐의 앞입니다. 테스트 코드가 `queue` 를 그대로 출력하므로 인스턴스 변수 이름을 바꾸지 않습니다.

## 테스트 코드와 출력 예

은행에 온 순서대로 고객을 넣고, 가장 먼저 온 고객부터 업무를 처리하는 코드입니다.

```python
bank = Queue()
bank.enqueue("김철수")
bank.enqueue("이영희")
bank.enqueue("박민수")
print("현재 대기열:", bank.queue)
print("업무 처리 중인 고객:", bank.dequeue())
print("남은 대기 고객:", bank.queue)
```

```
현재 대기열: ['김철수', '이영희', '박민수']
업무 처리 중인 고객: 김철수
남은 대기 고객: ['이영희', '박민수']
```

```python
q = Queue()
print(q.dequeue())
print(q.front())
print(q.is_empty())
```

```
-1
-1
True
```

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

