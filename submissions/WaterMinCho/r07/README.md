# 7회차 미니 모의고사

> 프로그램(`python study.py`)에서 풀면 이 폴더의 `quiz.py` 와 `.py` 파일에 답이 자동으로 저장됩니다.

문항 18개(보강할 단원 9개) · 평균 레벨 2.1 · 단원: s17 4, s10 3, s15 3, s03 1, s04 1, s07 1, s11 1, s13 1, s16 1, s19 1, s21 1

## s03_Q10 (조건식과 제어문 · 출력 예측 · 3점)

다음 코드의 출력 결과를 그대로 적으세요.

```python
battery = 20
if battery >= 60:
    print("여유")
elif battery < 60 and battery >= 20:
    print("주의")
else:
    print("충전 필요")
print("점검 완료")
```

## s04_Q4 (리스트와 딕셔너리 · 객관식 · 2점)

다음 중 `print(type(v))` 의 출력이 `<class 'tuple'>` 이 **아닌** 것은?

1. `v = ()`
2. `v = ("a")`
3. `v = "a",`
4. `v = "a", "b"`

## s07_Q20 (함수(2) · 객관식 · 2점)

다음 네 프로그램을 각각 따로 실행했을 때 **오류가 발생하는** 것을 **모두 고르세요**.

**1번**

```python
count = 0

def show():
    print(count)

show()
```

**2번**

```python
count = 0

def show():
    print(count)
    count = 1

show()
```

**3번**

```python
def setup():
    global count
    count = 5

setup()
print(count)
```

**4번**

```python
def setup():
    count = 5

setup()
print(count)
```

## s10_Q17 (클래스(2) · 객관식 · 2점)

다음 코드가 있습니다. (`pass` 는 아무 일도 하지 않는 자리 채움 문장입니다)

```python
class Pet:
    def __init__(self, name):
        self.name = name


class Cat(Pet):
    def __init__(self, name, color):
        super().__init__(name)
        self.color = color


class Dog(Pet):
    pass
```

아래 중 **오류가 발생하는** 것은?

1. `print(Pet("나비").name)`
2. `print(Cat("나비", "흰색").color)`
3. `print(Dog("초코").name)`
4. `print(Dog("초코", "갈색").name)`

## s13_Q20 (예외 처리·문자열·람다·map · 출력 예측 · 3점)

다음 코드의 출력 결과를 그대로 적으세요.

```python
items = ["7", "seven", "70"]

def pick(i):
    try:
        return int(items[i]) // 2
    except IndexError:
        return "범위 밖"
    except ValueError:
        return "정수 아님"

print(pick(0))
print(pick(1))
print(pick(3))
print(pick(-1))
```

## s15_Q9 (고급 함수 · 출력 예측 · 3점)

다음 코드의 출력 결과를 그대로 적으세요.

```python
colors = ["red", "green", "blue"]
it = iter(colors)
print(next(it))
for c in it:
    print(c)
for c in it:
    print("again", c)
print("end")
```

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

## s17_Q6 (알고리즘(2) · 객관식 · 2점)

그래프에 사이클(몇 개의 엣지를 지나 출발한 노드로 돌아오는 길)이 있을 때, DFS 가 같은 노드를 끝없이 다시 탐색하지 않게 처리하는 방법은?

1. BFS 로 전환한다.
2. 방문한 노드를 기록하여 이미 방문한 노드는 탐색하지 않는다.
3. 사이클을 무시하고 탐색을 계속한다.
4. 재귀 깊이를 제한한다.

## s17_Q7 (알고리즘(2) · 출력 예측 · 3점)

다음 코드의 출력 결과를 그대로 적으세요.

```python
graph1 = {1: [2, 3, 5], 2: [1, 3], 3: [1, 2, 4], 4: [3, 5], 5: [1, 4]}
print(len(graph1))
print(graph1[3])
print(len(graph1[1]))
print(graph1[4][1])
```

## s19_Q21 (statsmodels·scikit-learn·SciPy · 객관식 · 2점)

다음 코드로 학습한 `model` 에서 회귀 계수(절편과 기울기)를 꺼내고, 그 회귀식으로 x 가 7 일 때의 값을 예측했습니다. 세 값에 가장 가까운 것은?

```python
import statsmodels.api as sm

x = [1, 2, 3, 4, 5]
y = [2, 4, 6, 8, 10]

X = sm.add_constant(x)
model = sm.OLS(y, X).fit()
```

1. 절편 2, 기울기 0, 예측값 2
2. 절편 2, 기울기 2, 예측값 16
3. 절편 0, 기울기 2, 예측값 14
4. 절편 0, 기울기 10, 예측값 70

## s21_Q10 (파이썬 활용 심화(os·pathlib·JSON) · 단답 · 3점)

`docs` 폴더에서 확장자가 `.txt` 인 항목만 출력하는 코드입니다. 빈칸(`____`)에 들어갈 속성 이름을 적으세요.

```python
from pathlib import Path

path = Path("docs")
for item in path.iterdir():
    if item.____ == ".txt":
        print(item)
```

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

## s10_p11 (클래스(2) · 출력 · 정사각형은 직사각형이다 · 6점)

파일: `s10_p11.py`

아래 `Rect` 클래스가 이미 작성되어 있습니다(시작 코드에 포함).

```python
class Rect:
    kind = "직사각형"

    def __init__(self, width, height):
        self.width = width
        self.height = height
        print("도형 생성")

    def area(self):
        return self.width * self.height

    def info(self):
        print(self.kind, self.area())
```

`Rect` 를 **상속받는** `Square` 클래스를 정의하세요. 정사각형은 가로와 세로가 같은 직사각형입니다.

- 생성자는 `Square(side)` 처럼 한 변의 길이 **하나만** 받습니다. 안에서 **부모의 `__init__`** 을 호출해 `width` 와 `height` 에 모두 `side` 가 저장되게 합니다. (부모 `__init__` 이 출력하는 `도형 생성` 도 그대로 나와야 합니다)
- 클래스 변수 `kind` 를 `정사각형` 으로 다시 선언합니다.
- `area()` 와 `info()` 는 새로 만들지 않습니다. 부모의 것을 그대로 씁니다.
- `Rect` 클래스는 고치지 않습니다. 채점할 때는 아래와 같은 테스트 코드가 객체를 만들어 메서드를 호출합니다.

## 테스트 코드와 출력 예

```python
s = Square(4)
s.info()
```

```
도형 생성
정사각형 16
```

```python
r = Rect(2, 5)
r.info()
s = Square(5)
s.info()
print(Rect.kind, Square.kind)
```

```
도형 생성
직사각형 10
도형 생성
정사각형 25
직사각형 정사각형
```

## 제한 사항
- `side`, `width`, `height` 는 1 이상 100 이하의 정수

## s11_p09 (GUI 프로그래밍(PyQt6 · tkinter) · 반환값 · 격자 배치를 표로 적기 · 8점)

파일: `s11_p09.py`

`QGridLayout` 에 `layout.addWidget(위젯, row, column)` 으로 위젯들을 놓았을 때, 격자의 각 칸에 무엇이 들어 있는지를 행마다 문자열 하나로 적어 반환하는 `solution` 함수를 완성하세요.

- `names` 는 위젯에 적힌 글자 리스트, `rows` 는 같은 순서의 행 번호 리스트, `cols` 는 같은 순서의 열 번호 리스트입니다. `i` 번째 위젯은 `layout.addWidget(위젯, rows[i], cols[i])` 로 놓였습니다. 세 리스트의 길이는 같습니다.
- 행 번호와 열 번호는 0부터 셉니다. 격자의 행 수는 가장 큰 행 번호에 1 을 더한 값이고, 열 수는 가장 큰 열 번호에 1 을 더한 값입니다.
- 행마다 문자열을 하나 만듭니다. 그 행의 칸을 0번 열부터 마지막 열까지 차례로 적고, 칸과 칸 사이에 공백을 하나 둡니다. 위젯이 놓인 칸에는 그 위젯의 글자를, 비어 있는 칸에는 마침표 `.` 를 적습니다. 문자열의 맨 앞과 맨 뒤에는 공백을 넣지 않습니다.
- 만든 문자열을 0번 행부터 차례로 담은 리스트를 반환합니다.
- 함수 이름과 매개변수는 바꾸지 않습니다. `print` 가 아니라 `return` 으로 돌려줍니다.

## 제한 사항
- 리스트 길이는 1 이상 10 이하
- 위젯의 글자는 공백이 없는 1글자 이상의 문자열이고 `.` 은 쓰지 않습니다.
- 0 ≤ 행 번호, 열 번호 ≤ 4
- 같은 칸에 위젯이 두 개 놓이는 입력은 주어지지 않습니다. 위젯이 행·열 순서로 정렬되어 주어지지는 않습니다.

## 입출력 예

| names | rows | cols | 반환값 |
|---|---|---|---|
| `["수량", "입력", "확인", "취소"]` | `[0, 0, 1, 1]` | `[0, 1, 1, 2]` | `["수량 입력 .", ". 확인 취소"]` |
| `["A"]` | `[0]` | `[0]` | `["A"]` |
| `["닫기"]` | `[2]` | `[1]` | `[". .", ". .", ". 닫기"]` |

- 첫 번째 예: 가장 큰 행 번호가 1, 가장 큰 열 번호가 2 이므로 2행 3열입니다. 0번 행의 2번 열과 1번 행의 0번 열에는 위젯이 없어 `.` 이 들어갑니다.
- 세 번째 예: 위젯은 하나뿐이지만 2번 행 1번 열에 놓였으므로 격자는 3행 2열입니다.

## s15_p11 (고급 함수 · 출력 · 배수만 돌려주는 자식 이터레이터 · 8점)

파일: `s15_p11.py`

`Steps(stop)` 은 1, 2, …, `stop` 을 차례로 돌려주는 이터레이터 클래스이고, 시작 코드에 완성되어 있습니다.
`Steps` 를 상속한 `Multiples(stop, k)` 클래스를 완성하세요. `Multiples` 객체는 1 부터 `stop` 까지의 수 가운데 **`k` 의 배수만** 작은 것부터 돌려줍니다.

```python
class Steps:
    def __init__(self, stop):
        self.n = 0
        self.stop = stop

    def __iter__(self):
        return self

    def __next__(self):
        if self.n >= self.stop:
            raise StopIteration
        self.n += 1
        return self.n


class Multiples(Steps):
    # 여기에 __init__ 과 __next__ 를 작성하세요
    pass
```

- `Steps` 클래스는 고치지 않습니다.
- `Multiples` 의 `__init__(self, stop, k)` 는 `stop` 을 부모의 `__init__` 에 넘겨 저장하고, `k` 를 `self.k` 에 저장합니다.
- `__next__` 를 재정의해 `k` 의 배수가 아닌 값은 건너뜁니다. 부모의 `__next__` 는 `super().__next__()` 로 부를 수 있습니다.
- `stop` 이 `k` 의 배수이면 `stop` 도 돌려줍니다. 돌려줄 배수가 더 없으면 `next()` 에서 `StopIteration` 예외가 나야 합니다.
- `k` 는 1 이상의 정수, `stop` 은 0 이상의 정수입니다.

## 테스트 코드와 출력 예

```python
for x in Multiples(10, 3):
    print(x)
```

```
3
6
9
```

```python
m = Multiples(5, 5)
print(next(m))
try:
    next(m)
except StopIteration:
    print("stop")
```

```
5
stop
```

```python
print(list(Multiples(7, 2)))
print(list(Multiples(2, 3)))
```

```
[2, 4, 6]
[]
```

## s15_p16 (고급 함수 · 출력 · range 처럼 세는 이터레이터 클래스 · 8점)

파일: `s15_p16.py`

내장 `range()` 처럼 `start` 부터 `step` 씩 건너뛰며 `stop` 앞까지의 정수를 하나씩 돌려주는 이터레이터 클래스 `MyRange` 를 작성하세요.

- `MyRange(start, stop, step)` 으로 객체를 만듭니다. `step` 을 생략하면 1 로 봅니다.
- `__iter__` 와 `__next__` 메서드를 구현합니다. `__iter__` 는 자기 자신을 돌려줍니다.
- `stop` 은 돌려주지 않습니다. `MyRange(0, 6, 2)` 는 0, 2, 4 를 돌려줍니다.
- `step` 이 음수이면 값이 줄어드는 방향으로 세고, 값이 `stop` 보다 큰 동안만 돌려줍니다. `MyRange(10, 0, -3)` 은 10, 7, 4, 1 을 돌려줍니다.
- 돌려줄 값이 없으면 `next()` 에서 `StopIteration` 예외가 나야 합니다. `MyRange(5, 1, 1)` 처럼 처음부터 돌려줄 값이 없는 경우에도 첫 `next()` 에서 이 예외가 납니다.
- `start`, `stop`, `step` 은 정수이고 `step` 은 0 이 아닙니다.

## 테스트 코드와 출력 예

```python
for x in MyRange(0, 5, 1):
    print(x)
```

```
0
1
2
3
4
```

```python
for x in MyRange(1, 10, 3):
    print(x, end=" ")
print("end")
for x in MyRange(10, 0, -3):
    print(x, end=" ")
print("end")
```

```
1 4 7 end
10 7 4 1 end
```

```python
r = MyRange(2, 5)
print(next(r))
print(next(r))
print(next(r))
try:
    next(r)
except StopIteration:
    print("stop")
```

```
2
3
4
stop
```

## s17_p04 (알고리즘(2) · 출력 · 지도를 리스트로 만들어 출력 · 4점)

파일: `s17_p04.py`

아래 그림은 가로 6칸, 세로 6칸의 지도입니다. `□` 는 길이고 `■` 는 벽입니다.

```
□ ■ ■ ■ ■ ■
□ ■ □ □ □ ■
□ ■ □ ■ □ ■
□ ■ □ ■ □ □
□ □ □ ■ ■ □
■ ■ ■ ■ ■ □
```

길은 `0`, 벽은 `1` 로 표현한 2차원 리스트 `graph` 를 만들고, 지도의 가로 한 줄을 한 줄에 하나씩 리스트 모양 그대로 출력하는 프로그램을 작성하세요.

- `graph` 의 요소 하나가 지도의 가로 한 줄입니다. 맨 윗줄부터 차례로 넣습니다.
- 입력은 없습니다.

## 출력 예

```
[0, 1, 1, 1, 1, 1]
[0, 1, 0, 0, 0, 1]
[0, 1, 0, 1, 0, 1]
[0, 1, 0, 1, 0, 0]
[0, 0, 0, 1, 1, 0]
[1, 1, 1, 1, 1, 0]
```

- 출력은 글자 하나까지 같아야 합니다(대괄호, 쉼표 뒤 공백 포함).

## s17_p05 (알고리즘(2) · 반환값 · 엣지의 수 세기 · 4점)

파일: `s17_p05.py`

무방향 그래프가 딕셔너리 `graph` 로 주어집니다. 키는 노드이고 값은 그 노드와 연결된 노드의 리스트입니다.
이 그래프의 엣지가 모두 몇 개인지 정수로 **반환(return)** 하는 `solution` 함수를 완성하세요.

- 무방향 그래프라서 노드 1 과 2 를 잇는 엣지는 1 의 리스트와 2 의 리스트에 한 번씩, 모두 두 번 적혀 있습니다. 이 엣지는 1 개로 셉니다.
- 함수 이름과 매개변수는 바꾸지 않습니다. `print` 가 아니라 `return` 으로 돌려줍니다.

## 제한 사항
- 노드는 1 개 이상 20 개 이하
- 같은 두 노드를 잇는 엣지는 하나뿐이고, 자기 자신과 이어진 노드는 없습니다.

## 입출력 예

| graph | 반환값 |
|---|---|
| `{1: [2, 3, 5], 2: [1, 3], 3: [1, 2, 4], 4: [3, 5], 5: [1, 4]}` | `6` |
| `{1: [2], 2: [1]}` | `1` |
| `{1: [], 2: [], 3: []}` | `0` |

첫 번째 예의 엣지는 1-2, 1-3, 1-5, 2-3, 3-4, 4-5 로 6 개입니다.

