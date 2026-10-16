# 6회차 미니 모의고사

> 프로그램(`python study.py`)에서 풀면 이 폴더의 `quiz.py` 와 `.py` 파일에 답이 자동으로 저장됩니다.

문항 18개(보강할 단원 10개) · 평균 레벨 1.9 · 단원: s11 3, s15 2, s17 2, s18 2, s20 2, s01 1, s04 1, s13 1, s14 1, s16 1, s19 1, s21 1

## s01_Q3 (파이썬 소개 및 환경설정 · 객관식 · 2점)

IDLE 의 대화형 셸에서 명령을 실행했더니 아래와 같이 표시되었습니다. 이 결과와 대처 방법에 대한 설명으로 **옳지 않은** 것은?

```
>>> Print('Hello ROKEY')
Traceback (most recent call last):
  File "<pyshell#0>", line 1, in <module>
    Print('Hello ROKEY')
NameError: name 'Print' is not defined
```

1. 오류가 발생한 명령과 그 위치(1번째 줄)를 확인할 수 있다.
2. 마지막 줄에서 오류의 종류(`NameError`)와 내용을 확인할 수 있다.
3. `Print` 를 `print` 로 고치면 `Hello ROKEY` 가 출력된다.
4. 문자열을 작은따옴표로 감싼 것이 원인이므로, 큰따옴표로 바꾸면 오류가 사라진다.
5. ChatGPT 가 만들어 준 코드에서 이런 오류가 나왔다면, 오류 메시지를 ChatGPT 에 입력해 질문하고 그 답을 바탕으로 코드를 고쳐 다시 실행해 본다.

## s13_Q21 (예외 처리·문자열·람다·map · 출력 예측 · 3점)

다음 코드의 출력 결과를 그대로 적으세요.

```python
def parse(text):
    try:
        n = int(text)
        print("변환:", n)
        return n
    finally:
        print("parse 종료")

try:
    total = parse("8") + parse("x")
    print("합계:", total)
except ValueError:
    print("정수가 아닙니다")
```

## s14_Q13 (정규표현식 · 단답 · 3점)

`\D` 와 같은 뜻을 대괄호 `[ ]` 문자 클래스로 적으세요. (숫자 범위는 `0-9` 로 표현)

## s15_Q23 (고급 함수 · 출력 예측 · 3점)

다음 코드의 출력 결과를 그대로 적으세요.

```python
def mygen():
    for i in range(1, 1000):
        result = i * i
        yield result

gen = mygen()
print(next(gen))
print(next(gen))
print(next(gen))
```

## s17_Q21 (알고리즘(2) · 단답 · 3점)

노드 집합 `V` 와 엣지 집합 `E` 가 아래처럼 주어진 무방향 그래프 `G = (V, E)` 에서 노드 `3` 의 차수(degree)를 숫자로 적으세요.

```
V = {1, 2, 3, 4, 5}
E = {(1, 2), (1, 3), (1, 5), (2, 3), (3, 4), (3, 5), (4, 5)}
```

## s18_Q1 (Pandas·NumPy·Matplotlib · 객관식 · 2점)

Pandas 에서 데이터프레임(DataFrame)을 생성하는 데 사용하는 함수는?

1. `pd.Series()`
2. `pd.DataFrame()`
3. `pd.Array()`
4. `pd.Table()`

## s18_Q15 (Pandas·NumPy·Matplotlib · 객관식 · 2점)

NumPy 에서 `(3, 3)` 같은 모양을 넘기면 그 모양대로 모든 요소가 0 으로 초기화된 배열을 만드는 함수는?

1. `np.empty()`
2. `np.zeros_like()`
3. `np.zeros()`
4. `np.zeros_array()`

## s19_Q11 (statsmodels·scikit-learn·SciPy · 객관식 · 2점)

다음은 `mtcars` 데이터로 마력(`hp`)과 중량(`wt`)이 연비(`mpg`)에 미치는 영향을 분석하는 다중 선형 회귀 코드입니다. (가)와 (나)에 들어갈 코드로 옳은 것은?

```python
import statsmodels.api as sm

data = sm.datasets.get_rdataset("mtcars").data
X = (가)
y = data['mpg']
X = sm.add_constant(X)
model = (나)
print(model.summary())
```

1. (가) `data['hp', 'wt']` (나) `sm.OLS(y, X).fit()`
2. (가) `data[['hp', 'wt']]` (나) `sm.OLS(X, y).fit()`
3. (가) `data[['hp', 'wt']]` (나) `sm.OLS(y, X).fit()`
4. (가) `data[['hp', 'wt']]` (나) `sm.OLS(y, X)`

## s20_Q11 (Seaborn·OpenCV · 객관식 · 2점)

Seaborn 의 `tips` 데이터셋에는 요일(`day`) 열과 전체 금액(`total_bill`) 열이 있습니다. x 축에 요일, y 축에 전체 금액을 놓은 상자 그림(박스 플롯)을 그리려고 합니다. 빈칸에 들어갈 코드는?

```python
import seaborn as sns
import matplotlib.pyplot as plt

tips = sns.load_dataset("tips")
____
plt.show()
```

1. `sns.box(data=tips, x="day", y="total_bill")`
2. `sns.boxplot(data=tips, x=day, y=total_bill)`
3. `sns.boxplot(data=tips, x="day", y="total_bill")`
4. `sns.boxplot(data="tips", x="day", y="total_bill")`

## s20_Q28 (Seaborn·OpenCV · 객관식 · 2점)

OpenCV 함수와 하는 일의 연결이 옳지 **않은** 것은?

1. `cv2.inRange()`: 이미지의 크기를 지정한 범위 안으로 줄인다.
2. `cv2.GaussianBlur()`: 노이즈를 줄이고 이미지를 부드럽게 만든다.
3. `cv2.warpAffine()`: 변환 행렬을 받아 이미지를 변환한다.
4. `cv2.destroyAllWindows()`: 화면에 띄운 창을 닫는다.

## s21_Q1 (파이썬 활용 심화(os·pathlib·JSON) · 객관식 · 2점)

`os` 모듈에서 현재 작업 디렉터리를 **변경**하는 함수는?

1. `os.getcwd()`
2. `os.listdir()`
3. `os.chdir()`
4. `os.mkdir()`

## s04_p10 (리스트와 딕셔너리 · 출력 · 성적표 딕셔너리 · 8점)

파일: `s04_p10.py`

학생 이름과 세 과목 점수를 입력받아 성적표 딕셔너리를 만들고 합격 여부를 출력하는 프로그램을 작성하세요.

## 입력

- 첫째 줄: 이름(문자열)
- 둘째 줄 ~ 넷째 줄: 점수(0 이상 100 이하의 정수)가 한 줄에 하나씩, 모두 3개

## 처리

1. 점수 3개를 입력받은 순서대로 담은 리스트를 만듭니다. 점수는 정수로 저장합니다.
2. 아래 세 개의 키를 이 순서대로 가진 딕셔너리를 만듭니다.
   - `'이름'` : 입력받은 이름
   - `'점수'` : 점수 리스트
   - `'총점'` : 세 점수의 합
3. 첫째 줄에 딕셔너리를 그대로 출력합니다.
4. 둘째 줄에 총점이 180 **이상**이면 `합격`, 아니면 `불합격` 을 출력합니다.

## 입출력 예 1

입력

```
민수
80
90
100
```

출력

```
{'이름': '민수', '점수': [80, 90, 100], '총점': 270}
합격
```

## 입출력 예 2

입력

```
태오
59
60
60
```

출력

```
{'이름': '태오', '점수': [59, 60, 60], '총점': 179}
불합격
```

## s11_p03 (GUI 프로그래밍(PyQt6 · tkinter) · 반환값 · 콤보박스의 현재 항목 · 4점)

파일: `s11_p03.py`

`QComboBox` 의 `currentText()` 가 하는 일을 흉내 냅니다. 콤보박스의 항목 리스트 `items` 와 현재 선택된 인덱스 `index` 가 주어질 때, 현재 선택된 항목의 문자열을 반환하는 `solution` 함수를 완성하세요.

- `index` 가 `0` 이상이고 항목 개수보다 작으면 그 위치의 항목을 반환합니다.
- 그 밖의 경우(항목이 하나도 없거나, `index` 가 음수이거나, 항목 개수 이상이면) 선택된 항목이 없는 것이므로 빈 문자열 `""` 을 반환합니다.
- 함수 이름과 매개변수는 바꾸지 않습니다. `print` 가 아니라 `return` 으로 돌려줍니다.

## 제한 사항
- `items` 의 길이는 0 이상 10 이하, 원소는 문자열
- -5 ≤ index ≤ 15 인 정수

## 입출력 예

| items | index | 반환값 |
|---|---|---|
| `["소", "중", "대"]` | `1` | `"중"` |
| `["소", "중", "대"]` | `0` | `"소"` |
| `["소", "중", "대"]` | `3` | `""` |
| `[]` | `0` | `""` |
| `["Option 1"]` | `-1` | `""` |

## s11_p04 (GUI 프로그래밍(PyQt6 · tkinter) · 반환값 · 체크된 메뉴 주문 요약 · 6점)

파일: `s11_p04.py`

체크박스로 피자 메뉴를 고르는 주문 프로그램에서, 주문 버튼을 눌렀을 때 만들 주문 요약 문자열을 반환하는 `solution` 함수를 완성하세요.

- `names` 는 메뉴 이름 리스트, `prices` 는 같은 순서의 가격 리스트, `checked` 는 같은 순서의 체크 여부(`True`/`False`) 리스트입니다. 세 리스트의 길이는 같습니다.
- 체크된 메뉴가 하나 이상이면 `"이름1, 이름2 = 총가격원"` 형식의 문자열을 반환합니다. 이름 사이는 쉼표와 공백(`, `)으로 잇고, 이름들과 `=` 사이, `=` 과 총가격 사이에 공백이 하나씩 있습니다. 이름 순서는 리스트 순서대로입니다.
- 체크된 메뉴가 하나도 없으면 `"선택된 메뉴가 없습니다."` 를 반환합니다.
- 함수 이름과 매개변수는 바꾸지 않습니다. `print` 가 아니라 `return` 으로 돌려줍니다.

## 제한 사항
- 리스트 길이는 1 이상 10 이하, 가격은 0 이상 100000 이하의 정수

## 입출력 예

| names | prices | checked | 반환값 |
|---|---|---|---|
| `["치즈", "불고기", "페퍼로니"]` | `[3000, 3500, 4000]` | `[True, False, True]` | `"치즈, 페퍼로니 = 7000원"` |
| `["치즈", "불고기", "페퍼로니"]` | `[3000, 3500, 4000]` | `[False, True, False]` | `"불고기 = 3500원"` |
| `["치즈", "불고기", "페퍼로니"]` | `[3000, 3500, 4000]` | `[False, False, False]` | `"선택된 메뉴가 없습니다."` |

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

## s15_p08 (고급 함수 · 출력 · 카운트다운 이터레이터 클래스 · 6점)

파일: `s15_p08.py`

`Countdown(start)` 객체를 for 문에 넣으면 `start`, `start - 1`, …, `1` 을 차례로 돌려주는 이터레이터 클래스를 완성하세요.
`__init__` 은 이미 작성되어 있으니 `__iter__` 와 `__next__` 메서드를 추가하면 됩니다.

- `start` 가 0 이면 아무 값도 돌려주지 않습니다.
- 값을 다 돌려준 뒤 `next()` 가 호출되면 `StopIteration` 예외를 일으켜야 합니다.
- 객체마다 따로 세어야 합니다(두 객체를 번갈아 써도 서로 영향이 없어야 합니다).

## 테스트 코드와 출력 예

```python
for x in Countdown(3):
    print(x)
```

```
3
2
1
```

```python
c = Countdown(2)
print(next(c))
print(next(c))
try:
    next(c)
except StopIteration:
    print("done")
```

```
2
1
done
```

```python
print(list(Countdown(4)))
print(list(Countdown(0)))
```

```
[4, 3, 2, 1]
[]
```

## s16_p05 (알고리즘(1) · 빈칸 채우기 · 큐 클래스 완성 · 6점)

파일: `s16_p05.py`

리스트를 이용해 큐를 구현한 `Queue` 클래스입니다. 빈칸(`____`) 3곳을 채워 클래스를 완성하세요.

| 메서드 | 하는 일 |
|---|---|
| `enqueue(data)` | `data` 를 큐의 맨 뒤에 넣습니다 |
| `dequeue()` | 가장 먼저 넣은 데이터를 꺼내서 반환합니다. 비어 있으면 `None` 을 반환합니다 |
| `is_empty()` | 비어 있으면 `True`, 아니면 `False` |
| `status_queue()` | 큐 리스트 전체를 반환합니다 |

- `dequeue()` 는 비어 있는지 확인하는 메서드를 먼저 호출해야 합니다.
- 빈칸만 채웁니다. 다른 줄을 고치거나 줄을 추가하면 오답 처리됩니다.

```python
class Queue:
    def __init__(self):
        self.queue = []

    def enqueue(self, data):
        self.queue.append(data)

    def dequeue(self):
        if not self.____():
            return self.queue.pop(____)
        return

    def is_empty(self):
        if ____ == 0:
            return True
        return False

    def status_queue(self):
        return self.queue
```

## 테스트 코드와 출력 예

```python
q = Queue()
q.enqueue(1)
q.enqueue(2)
q.enqueue(3)
print(q.dequeue())
print(q.status_queue())
```

```
1
[2, 3]
```

```python
q = Queue()
print(q.dequeue())
print(q.is_empty())
q.enqueue("x")
print(q.is_empty())
```

```
None
True
False
```

## s17_p08 (알고리즘(2) · 출력 · DFS와 BFS 결과 출력 · 6점)

파일: `s17_p08.py`

강의 연습 문제의 그래프 `g1` 이 시작 코드에 주어져 있습니다. 시작 노드 번호 `start` 를 입력받아, `g1` 을 깊이 우선 탐색(DFS)한 방문 순서와 너비 우선 탐색(BFS)한 방문 순서를 차례로 출력하는 프로그램을 작성하세요.

- 한 노드에서 갈 수 있는 노드가 여럿이면 `g1` 의 리스트에서 앞에 적힌 노드를 먼저 방문합니다.
- 이미 방문한 노드는 다시 방문하지 않습니다.
- 첫 줄에 `dfs:` 와 방문 순서 리스트를, 둘째 줄에 `bfs:` 와 방문 순서 리스트를 출력합니다. 콜론 뒤에 공백이 한 칸 있습니다.
- 시작 코드의 `g1` 과 `start` 를 입력받는 줄은 그대로 둡니다.

```python
g1 = {1: [2, 3, 4], 2: [1, 5], 3: [1, 6], 4: [1, 6], 5: [2, 6], 6: [3, 4, 5]}
start = int(input())

# 여기에 코드를 작성하세요
```

입력

- 시작 노드 번호 `start` (1 이상 6 이하의 정수)

## 입출력 예

입력

```
1
```

출력

```
dfs: [1, 2, 5, 6, 3, 4]
bfs: [1, 2, 3, 4, 5, 6]
```

입력

```
5
```

출력

```
dfs: [5, 2, 1, 3, 6, 4]
bfs: [5, 2, 6, 1, 3, 4]
```

- 출력은 글자 하나까지 같아야 합니다(콜론, 대괄호, 쉼표 뒤 공백 포함).

