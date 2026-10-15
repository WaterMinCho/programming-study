# 3회차 미니 모의고사

> 프로그램(`python study.py`)에서 풀면 이 폴더의 `quiz.py` 와 `.py` 파일에 답이 자동으로 저장됩니다.

문항 18개(보강할 단원 19개) · 평균 레벨 1.4 · 단원: s19 3, s04 2, s15 2, s18 2, s01 1, s06 1, s07 1, s08 1, s10 1, s11 1, s14 1, s20 1, s21 1

## s04_Q14 (리스트와 딕셔너리 · 단답 · 3점)

다음 코드를 실행한 뒤 `type(point)` 로 확인되는 자료형의 이름을 영어 소문자로 적으세요. (답 형식 예: `int`, `str`)

```python
point = 3.5, 7
```

## s07_Q17 (함수(2) · 객관식 · 2점)

다음 재귀 함수에서 **기저 조건**과 **재귀 단계**에 해당하는 줄을 바르게 짝지은 것은?

```python
def count_up(n):
    if n > 3:           # (가)
        return
    print(n)            # (나)
    count_up(n + 1)     # (다)

count_up(1)
```

1. 기저 조건 (가), 재귀 단계 (다)
2. 기저 조건 (나), 재귀 단계 (다)
3. 기저 조건 (다), 재귀 단계 (가)
4. 기저 조건 (가), 재귀 단계 (나)

## s15_Q1 (고급 함수 · 객관식 · 2점)

이터러블(iterable)과 이터레이터(iterator)에 대한 설명으로 옳지 **않은** 것은?

1. 이터러블은 `__iter__()` 메서드를 가지며, `iter()` 함수로 이터레이터를 얻을 수 있다.
2. 이터레이터는 `__next__()` 메서드를 가지며, `__iter__()` 는 자기 자신을 반환한다.
3. 리스트는 이터러블이지만 이터레이터는 아니다.
4. 이터레이터는 값을 끝까지 읽은 뒤에도 for 문을 다시 돌리면 처음부터 값을 다시 읽을 수 있다.

## s15_Q15 (고급 함수 · 객관식 · 2점)

다음 클래스로 만든 객체를 for 문에 넣었을 때 나오는 값을 **같은 순서로** 만드는 제너레이터 표현식은?

```python
class Squares:
    def __init__(self):
        self.n = 2

    def __iter__(self):
        return self

    def __next__(self):
        if self.n > 5:
            raise StopIteration
        value = self.n * self.n
        self.n += 1
        return value
```

1. `(i * i for i in range(2, 5))`
2. `(i * i for i in range(2, 6))`
3. `(i * i for i in range(1, 6))`
4. `(i * 2 for i in range(2, 6))`

## s18_Q15 (Pandas·NumPy·Matplotlib · 객관식 · 2점)

NumPy 에서 `(3, 3)` 같은 모양을 넘기면 그 모양대로 모든 요소가 0 으로 초기화된 배열을 만드는 함수는?

1. `np.empty()`
2. `np.zeros_like()`
3. `np.zeros()`
4. `np.zeros_array()`

## s18_Q39 (Pandas·NumPy·Matplotlib · 객관식 · 2점)

CSV 파일과 엑셀 파일의 구조에 대한 설명으로 옳지 **않은** 것은?

1. CSV 파일은 줄바꿈으로 구분되는 행(레코드)으로 이루어지고, 각 행은 쉼표로 구분되는 열(필드)로 이루어진다.
2. CSV 파일은 텍스트 에디터에 내용을 적고 확장자를 `.csv` 로 저장해 만들 수 있다.
3. 엑셀 파일은 북(book)이라고 부르며, 북 하나에는 시트(sheet)를 하나만 둘 수 있다.
4. 엑셀의 시트는 행(row)과 열(column)을 가진 2차원 셀(cell)로 이루어진다.

## s19_Q6 (statsmodels·scikit-learn·SciPy · 객관식 · 2점)

SciPy 의 서브모듈과 그 모듈이 다루는 분야의 짝으로 옳지 **않은** 것은?

1. `scipy.sparse` 는 통계
2. `scipy.linalg` 는 선형대수
3. `scipy.optimize` 는 최적화
4. `scipy.integrate` 는 적분

## s19_Q9 (statsmodels·scikit-learn·SciPy · 객관식 · 2점)

세 패키지에 대한 설명으로 옳지 **않은** 것은?

1. statsmodels 는 선형 회귀와 로지스틱 회귀 분석, ARIMA 모델을 포함한 시계열 분석, 가설 검정 같은 통계적 테스트 기능을 제공하고, 강의에서는 `import statsmodels.api as sm` 으로 불러왔다.
2. scikit-learn 은 파이썬 기반의 머신러닝 라이브러리이고, `pip install scikit-learn` 으로 설치한 뒤 `import scikit-learn as sk` 로 불러온다.
3. scikit-learn 의 모델은 종류가 달라도 `fit(X, y)`, `predict(X)`, `score(X, y)` 같은 공통 메서드를 쓴다.
4. SciPy 는 과학 및 공학 계산 라이브러리이고 NumPy 위에 구축되어 있다.

## s19_Q36 (statsmodels·scikit-learn·SciPy · 객관식 · 2점)

강의에 나온 이름과 그 설명의 짝으로 옳지 **않은** 것은?

1. `OLS` 는 Ordinary Least Squares 의 줄임말이고, 오차의 제곱을 최소화하는 기울기와 절편을 추정하는 방식이다.
2. `SVC` 는 서포트 벡터 분류(Support Vector Classification)이고, 최대 마진을 가진 최적의 선(평면)을 찾아 데이터를 분류한다.
3. `metrics` 는 성능 지표를 모아 둔 모듈이고, `accuracy_score()` 가 정답률을 계산한다.
4. `fit()` 은 시험 데이터에 대해 분류를 수행하고, `predict()` 는 훈련 데이터에 따라 모델을 피팅한다.

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

## s21_Q13 (파이썬 활용 심화(os·pathlib·JSON) · 객관식 · 2점)

새 엑셀 파일을 만들어 `data.xlsx` 로 저장하는 코드입니다. 빈칸(`____`)에 들어갈 메서드는?

```python
from openpyxl import Workbook

wb = Workbook()
sheet = wb.active
sheet['A1'] = 'Hello'
wb.____('data.xlsx')
```

1. `to_excel`
2. `save`
3. `write`
4. `dump`

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

## s04_p08 (리스트와 딕셔너리 · 반환값 · 세 과목 평균 · 6점)

파일: `s04_p08.py`

학생 한 명의 정보가 딕셔너리 `student` 로 주어집니다.

- `"name"` 키 : 이름(문자열)
- `"scores"` 키 : 세 과목 점수가 담긴 리스트(정수 3개)

세 점수의 평균을 반환하는 `solution` 함수를 완성하세요.

- 함수 이름과 매개변수는 바꾸지 않습니다.
- 평균은 합을 `/` 로 나눈 **실수(float)** 로 반환합니다. 예를 들어 `90.0` 이며, 정수 `90` 은 오답입니다.

## 제한 사항
- `"scores"` 리스트의 길이는 항상 3
- 각 점수는 0 이상 100 이하의 정수

## 입출력 예

| student | 반환값 |
|---|---|
| `{'name': '지호', 'scores': [80, 90, 100]}` | `90.0` |
| `{'name': '서연', 'scores': [70, 75, 80]}` | `75.0` |

## s06_p06 (함수(1) · 반환값 · 배수의 합 · 6점)

파일: `s06_p06.py`

정수 `n`, `limit` 가 주어질 때, 1 이상 `limit` 이하의 정수 중 `n` 의 배수를 모두 더한 값을 반환하는
`solution` 함수를 완성하세요. 해당하는 수가 하나도 없으면 0 을 반환합니다.

- 함수 이름과 매개변수는 바꾸지 않습니다.

## 제한 사항
- 1 ≤ n ≤ 9
- 1 ≤ limit ≤ 1000

## 입출력 예

| n | limit | 반환값 | 설명 |
|---|---|---|---|
| 3 | 10 | 18 | 3 + 6 + 9 |
| 5 | 5 | 5 | limit 자신도 포함 |
| 7 | 6 | 0 | 6 이하에는 7 의 배수가 없음 |
| 1 | 10 | 55 | 1 부터 10 까지의 합 |

## s08_p07 (자료구조와 알고리즘 · 출력 · 최댓값과 최솟값 · 6점)

파일: `s08_p07.py`

정수 N개를 입력받아 리스트에 저장한 뒤, 그중 가장 큰 값과 가장 작은 값을 찾아 출력하는 프로그램을 작성하세요.

강의에서 배운 방법대로, 첫 번째 값을 기준으로 잡고 반복문과 `if` 비교로 직접 구해 보세요.

## 입력

- 첫째 줄에 정수의 개수 N(1 ≤ N ≤ 100)이 주어집니다.
- 둘째 줄부터 N개의 줄에 -1000 이상 1000 이하의 정수가 하나씩 주어집니다.

## 출력

- 첫째 줄: `최댓값:` 뒤에 한 칸 띄고 가장 큰 값
- 둘째 줄: `최솟값:` 뒤에 한 칸 띄고 가장 작은 값

## 입출력 예

입력

```
5
23
8
61
15
34
```

출력

```
최댓값: 61
최솟값: 8
```

입력

```
3
-7
-2
-9
```

출력

```
최댓값: -2
최솟값: -9
```

## s10_p04 (클래스(2) · 빈칸 채우기 · 노트북은 기기다 · 6점)

파일: `s10_p04.py`

제품 이름과 가격을 저장하는 `Device` 클래스와, 이를 **상속받아** 램 용량(`ram`)을 추가한 `Laptop` 클래스입니다.
빈칸(`____`) 3곳을 채워 클래스를 완성하세요.

- `Laptop` 의 `__init__` 은 **부모의 `__init__`** 을 호출해 `name`, `price` 를 저장하게 하고, 이어서 `ram` 을 인스턴스 변수에 저장합니다.
- **빈칸만** 채웁니다. 다른 줄을 고치거나 줄을 추가하면 오답 처리됩니다.

```python
class Device:
    def __init__(self, name, price):
        self.name = name
        self.price = price

    def info(self):
        print("제품:", self.name)
        print("가격:", self.price)


class Laptop(____):
    def __init__(self, name, price, ram):
        ____.__init__(name, price)
        self.ram = ____
```

## 테스트 코드와 출력 예

```python
l = Laptop("그램", 1500000, 16)
l.info()
print(l.ram)
```

```
제품: 그램
가격: 1500000
16
```

```python
l = Laptop("맥북", 2000000, 8)
print(l.name, l.price, l.ram)
```

```
맥북 2000000 8
```

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

## s14_p08 (정규표현식 · 반환값 · 대소문자 무시 세기 · 6점)

파일: `s14_p08.py`

문자열 `text` 와 찾을 단어 `word` 가 주어질 때, `word` 가 `text` 안에 대소문자 구별 없이 몇 번 나오는지
세어 정수로 **반환(return)** 하는 `solution` 함수를 완성하세요.

- 다른 단어의 일부로 들어 있어도 셉니다. `"Okay"` 안의 `ok` 도 한 번입니다.
- `word` 는 영문자만으로 이루어져 있고, 겹쳐서 세는 경우는 없습니다.
- 한 번도 나오지 않으면 `0` 을 반환합니다.
- 함수 이름과 매개변수는 바꾸지 않습니다. `print` 가 아니라 `return` 으로 돌려줍니다.

## 입출력 예

| text | word | 반환값 |
|---|---|---|
| `"Python python PYTHON"` | `"python"` | `3` |
| `"ok OK Okay"` | `"ok"` | `3` |
| `"banana"` | `"NA"` | `2` |
| `"hello"` | `"x"` | `0` |

