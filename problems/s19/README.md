# 19차시 · 딥러닝 파이썬 패키지(2)

통계 분석에 쓰는 statsmodels, 머신러닝에 쓰는 scikit-learn, 과학 계산에 쓰는 SciPy 의 사용 순서와 함수 이름을 배우는 차시입니다.
세 패키지는 따로 설치해야 실행되므로, 시험에서는 함수와 클래스의 이름, 인자 순서, 빈칸에 들어갈 코드, 결과 읽는 법을 묻기 좋습니다.
차시 과제와 주간 과제도 이름을 고르는 객관식과 빈칸 채우기로 나왔습니다.

| 강의 절 | 내용 |
|---|---|
| 19.1 statsmodels | 선형 회귀 `H(x) = Wx + b`, `sm.add_constant` → `sm.OLS(y, X).fit()` → `summary()`, 결과 표 읽기 |
| 19.2 scikit-learn 개요 | 공통 메서드 `fit` · `predict` · `score`, XOR 학습(`svm.SVC`, `metrics.accuracy_score`) |
| 19.3 scikit-learn 활용 | 붓꽃 분류: `load_iris` → `train_test_split` → `fit` → `predict` → `accuracy_score` |
| 19.4 SciPy | `linalg.solve`, `optimize.minimize` · `root`, `stats.describe`, `sparse.csr_matrix` |

## 1. 세 패키지의 역할, 설치, 임포트

| 패키지 | 하는 일 | 설치 | 강의의 임포트 |
|---|---|---|---|
| statsmodels | 통계적 모델 추정, 가설 검정, 데이터 탐색 | `pip install statsmodels` | `import statsmodels.api as sm` |
| scikit-learn | 머신러닝(데이터 전처리, 모델링, 평가) | `pip install scikit-learn` | `import sklearn as sk` |
| SciPy | 과학·공학 계산 | `pip install scipy` | `import scipy as sp` |

- scikit-learn 은 설치할 때의 이름과 코드에서 부르는 이름이 서로 다릅니다. 설치는 `scikit-learn`, 임포트는 `sklearn` 입니다.
- statsmodels 는 `statsmodels.api` 를 `sm` 으로 불러옵니다. `.api` 를 빼고 `import statsmodels as sm` 으로 쓰면 `sm.OLS` 를 찾지 못합니다.
- statsmodels 의 주요 기능은 선형 회귀와 로지스틱 회귀 분석, 시계열 분석(ARIMA, 자기회귀 누적 이동 평균 모델), 통계적 테스트(가설 검정, 모델 선택, 변수 선택), 데이터 탐색 및 시각화입니다. 시계열은 시간의 흐름에 따라 기록된 데이터입니다. R 스타일 공식과 pandas 데이터프레임으로 모델을 지정할 수 있습니다.
- SciPy 는 NumPy 위에 만들어졌습니다. NumPy 는 다차원 배열과 기본 연산을 제공하고, SciPy 는 그 위에서 고급 수학·과학 계산 기능을 제공합니다.

## 2. 선형 회귀(Linear regression)

- 레이블(정답)이 들어 있는 데이터로 모델을 만들고, 그 모델에 새 데이터를 넣어 결과 값을 예측하는 방법입니다.
- 독립 변수와 종속 변수 사이의 선형 관계를 모델링합니다. 독립 변수는 다른 것의 영향을 받지 않는 변수(입력 x)이고, 종속 변수는 독립 변수에 따라 값이 변하는 변수(결과 y)입니다.
- 가설은 `H(x) = Wx + b` 로 나타냅니다. `W` 는 기울기, `b` 는 y 절편입니다. 데이터에 가장 가까운 직선이 되도록 `W` 와 `b` 를 찾는 일이 학습입니다.
- 강의의 예: 5시간 공부한 학생이 50점, 10시간 공부한 학생이 100점을 받았다면 7시간 공부한 학생은 70점으로 예측합니다.
- 회귀라는 말은 평균보다 크거나 작은 값들이 평균으로 돌아간다는 가정에서 나왔습니다.

## 3. statsmodels 로 선형 회귀 하기

```python
import statsmodels.api as sm

data = sm.datasets.get_rdataset("mtcars").data   # 자동차 32종의 데이터프레임
X = data['hp']                   # 독립 변수: 마력
y = data['mpg']                  # 종속 변수: 연비
X = sm.add_constant(X)           # 상수항(절편) 열 추가
model = sm.OLS(y, X).fit()       # 모델 생성 후 학습
print(model.summary())           # 결과 요약 표 출력
```

순서는 데이터 준비 → `add_constant` → `OLS(y, X)` → `fit()` → `summary()` 입니다.

- `sm.add_constant(X)` 는 독립 변수에 상수항(절편) 열을 추가합니다. 값이 모두 1 인 `const` 열이 맨 앞에 붙습니다.
- `sm.OLS(y, X)` 는 선형 회귀 모델을 만듭니다. 종속 변수 `y` 를 먼저, 독립 변수 `X` 를 나중에 적습니다. OLS 는 Ordinary Least Squares 의 줄임말로, 오차의 제곱을 최소화하는 기울기와 절편을 추정하는 방식입니다.
- `fit()` 이 모델을 학습하고, `summary()` 가 학습 결과를 요약한 표를 돌려줍니다. `fit()` 을 부르지 않은 `sm.OLS(y, X)` 에는 `summary()` 가 없습니다.
- 독립 변수가 여러 개인 다중 선형 회귀는 `X = data[['hp', 'wt']]` 처럼 대괄호를 두 겹으로 써서 열을 고릅니다. 나머지 줄은 단순 선형 회귀와 같습니다.
- `mtcars` 는 1974년 모터트랜드 US 매거진에서 가져온 자동차 32종의 데이터입니다. `mpg` 는 연비, `cyl` 은 실린더 수, `disp` 는 배기량, `hp` 는 마력입니다.

회귀 계수만 꺼낼 때는 `model.params` 를 씁니다. `add_constant` 가 상수항을 맨 앞에 붙였으므로 `params[0]` 이 절편, `params[1]` 이 기울기입니다.

```python
import numpy as np
import statsmodels.api as sm

X = np.array([1, 2, 3, 4, 5])
y = np.array([2, 4, 5, 4, 5])

X = sm.add_constant(X)
model = sm.OLS(y, X).fit()

W = model.params[1]              # 기울기
print("기울기 (coef):", W)       # 0.6 에 가까운 값
print(model.params[0])           # 절편, 2.2 에 가까운 값
```

- 실수 계산이라 `0.6000000000000001` 처럼 끝자리가 붙어 나올 수 있습니다.
- 손으로 검산할 때는 `W = Σ(x - x평균)(y - y평균) / Σ(x - x평균)²`, `b = y평균 - W × x평균` 을 씁니다. 위 데이터는 x평균 3, y평균 4 이고 `W = 6 / 10 = 0.6`, `b = 4 - 0.6 × 3 = 2.2` 입니다.
- x 가 `[1, 2, 3, 4, 5]`, y 가 `[2, 4, 6, 8, 10]` 이면 모든 점이 `y = 2x` 위에 있으므로 기울기는 2, 절편은 0 에 가까운 값이 나옵니다.
- `add_constant` 를 빼먹으면 절편 없이 원점을 지나는 직선으로 학습합니다. `params` 에 값이 하나만 들어가서 `params[1]` 은 `IndexError` 가 됩니다.
- 위처럼 NumPy 배열로 학습하면 `params` 도 배열이라 `params[1]` 처럼 번호로 꺼냅니다. mtcars 처럼 데이터프레임으로 학습하면 `params` 에 열 이름이 붙어서 `params['const']`, `params['hp']` 로 꺼냅니다.

데이터와 회귀 직선을 한 그림에 그릴 때는 18차시의 matplotlib 으로 데이터를 산점도 `plt.scatter` 로 찍고 직선을 `plt.plot` 으로 긋습니다.

```python
plt.scatter(x, y)                          # 데이터 점
plt.plot(x, W * x + b, color="red")        # 회귀 직선 H(x) = Wx + b
plt.title("Linear Regression")
plt.xlabel("x")
plt.ylabel("y")
plt.show()
```

## 4. 결과 표(OLS Regression Results) 읽기

`hp` 로 `mpg` 를 예측한 단순 선형 회귀의 요약표 일부입니다.

```text
Dep. Variable:      mpg      R-squared:         0.602
No. Observations:    32      Adj. R-squared:    0.589
Df Residuals:        30      AIC:               179.2
Df Model:             1      BIC:               182.2
-----------------------------------------------------
              coef    std err        t      P>|t|
const      30.0989      1.634   18.421      0.000
hp         -0.0682      0.010   -6.742      0.000
```

| 항목 | 뜻 | 읽는 법 |
|---|---|---|
| `No. Observations` | 총 표본 수 | 위 표는 32 |
| `Df Residuals` | 잔차의 자유도 | 표본 수에서 변수(종속변수와 독립변수)의 개수를 뺀 값. 32 - 2 = 30 |
| `Df Model` | 독립변수의 개수 | 위 표는 1 (상수항은 세지 않음) |
| `R-squared` | 결정 계수. 독립변수가 종속변수를 얼마나 설명하는지 | 0 에서 1 사이. 1 에 가까울수록 잘 설명. 0.602 면 약 60% |
| `Adj. R-squared` | 수정된 R 제곱 | 독립변수가 늘면 R 제곱이 커지는 문제를 독립변수 개수와 표본 크기로 조정한 값 |
| `F-statistic` | 회귀모델 전체가 통계적으로 유의한지 보는 값 | 클수록 유의 |
| `Prob (F-statistic)` | F 통계량의 p 값 | 0.05 이하이면 유의미 |
| `AIC`, `BIC` | 표본 수와 모델 복잡도로 모델을 평가한 값 | 낮을수록 좋음. BIC 는 복잡도에 벌점을 더 크게 줌 |
| `coef` | 회귀계수(절편과 기울기)의 추정치 | `const` 가 절편, 변수 이름 행이 기울기 |
| `std err` | 계수 추정치의 표준오차 | 작을수록 좋음 |
| `t` | 계수가 표준오차에 비해 얼마나 큰지 | 절댓값이 클수록 영향이 뚜렷 |
| `P>\|t\|` | 계수가 0 이라는 가설에서 이런 t 값이 나올 확률 | 0.05 보다 작으면 유의미 |

- `coef` 의 `const` 가 30.0989, `hp` 가 -0.0682 이므로 회귀식은 `H(x) = -0.0682 * x + 30.0989` 입니다. 마력이 1 오를 때마다 연비가 0.0682 줄어든다고 해석합니다.
- 회귀식에 값을 넣으면 예측이 됩니다. 마력이 100 이면 `30.0989 - 0.0682 × 100 = 23.2789` 입니다.
- 독립변수를 `hp`, `wt` 두 개로 늘리면 `Df Model` 은 2, `Df Residuals` 는 32 - 3 = 29 가 됩니다.
- F 통계량은 모델 전체의 유의성을, t 통계량은 독립변수 하나하나의 영향을 봅니다.

## 5. scikit-learn 개요와 XOR 학습

- 파이썬 기반의 머신러닝 라이브러리이고 분류, 회귀, 클러스터링 알고리즘을 지원합니다.
- 모델의 종류가 달라도 `fit(X, y)` 로 학습하고 `predict(X)` 로 예측하고 `score(X, y)` 로 평가합니다. 입력과 출력은 NumPy 배열, pandas 데이터프레임 같은 표준 자료구조를 씁니다.
- `fit(X, y)` 는 데이터를 먼저, 레이블(정답)을 나중에 적습니다. statsmodels 의 `sm.OLS(y, X)` 와 순서가 반대입니다.

XOR(배타적 논리합)은 두 입력 가운데 하나만 참일 때 참이고, 둘 다 참이거나 둘 다 거짓이면 거짓입니다.

| P | Q | P xor Q |
|---|---|---|
| 0 | 0 | 0 |
| 1 | 0 | 1 |
| 0 | 1 | 1 |
| 1 | 1 | 0 |

```python
from sklearn import svm
from sklearn import metrics

clf = svm.SVC()                                   # 알고리즘 선택
clf.fit([[0, 0], [0, 1], [1, 0], [1, 1]],         # 학습 데이터
        [0, 1, 1, 0])                             # 학습 레이블
pre = clf.predict([[0, 1], [1, 1]])               # 예측
print(pre)                                        # [1 0]
ac_score = metrics.accuracy_score([1, 0], pre)    # 정답과 예측을 비교
print(f"정답률: {ac_score}")                      # 정답률: 1.0
```

- `predict` 의 결과는 NumPy 배열이라 `[1 0]` 처럼 쉼표 없이 출력됩니다.
- `accuracy_score(정답, 예측)` 은 맞힌 개수를 전체 개수로 나눈 값입니다. 전부 맞히면 `1.0`, 4개 가운데 3개를 맞히면 `0.75` 입니다. 100 을 곱한 퍼센트 값이 아닙니다.
- `predict` 에는 `[[0, 1], [1, 1]]` 처럼 데이터 한 건이 한 행인 2차원 자료를 넘깁니다.

데이터를 한 표에 모아 두었다면 pandas 로 학습 데이터와 레이블을 나눕니다.

```python
import pandas as pd

xor_data = [
    [0, 0, 0],
    [0, 1, 1],
    [1, 0, 1],
    [1, 1, 0]
]
xor_df = pd.DataFrame(xor_data)
data = xor_df.loc[:, 0:1]        # 모든 행, 0번 열부터 1번 열까지 (P, Q)
label = xor_df.loc[:, 2]         # 모든 행, 2번 열 (정답)

clf = svm.SVC()
clf.fit(data, label)
pre = clf.predict(data)
print("예측결과:", pre)                           # 예측결과: [0 1 1 0]
print(f"정답률= {metrics.accuracy_score(label, pre)}")   # 정답률= 1.0
```

`loc` 의 슬라이스는 끝 라벨을 포함합니다. `0:1` 은 0번 열과 1번 열 두 개를 고릅니다.

## 6. 붓꽃 품종 분류

꽃받침(sepal)과 꽃잎(petal)의 길이와 너비로 붓꽃의 품종을 맞히는 예제입니다. 붓꽃은 품종이 150종류 이상이고, 예제는 공개된 Fisher 의 붓꽃 데이터를 씁니다.

```python
from sklearn.datasets import load_iris
from sklearn.model_selection import train_test_split
from sklearn import svm, metrics
import pandas as pd

# 1. 데이터셋 로드
iris = load_iris()
df = pd.DataFrame(data=iris.data, columns=iris.feature_names)
df['target'] = iris.target                  # 0, 1, 2

# 2. 필요한 열 추출
iris_data = df[["sepal length (cm)", "sepal width (cm)",
                "petal length (cm)", "petal width (cm)"]]
iris_label = df["target"]

# 3. 학습용과 테스트용으로 나누기
train_data, test_data, train_label, test_label = \
    train_test_split(iris_data, iris_label)

# 4. 학습과 예측
clf = svm.SVC()
clf.fit(train_data, train_label)
pre = clf.predict(test_data)

# 5. 정답률
ac_score = metrics.accuracy_score(test_label, pre)
print("정답률 =", ac_score)                 # 정답률 = 0.9473684210526315 (실행마다 달라짐)
```

| 단계 | 모듈 | 쓰는 것 |
|---|---|---|
| 데이터 로드 | `sklearn.datasets` | `load_iris()` |
| 데이터 나누기 | `sklearn.model_selection` | `train_test_split(데이터, 레이블)` |
| 학습과 예측 | `sklearn.svm` | `SVC()`, `fit(훈련 데이터, 훈련 레이블)`, `predict(시험 데이터)` |
| 정답률 | `sklearn.metrics` | `accuracy_score(시험 레이블, 예측)` |

- `iris.data` 는 붓꽃 150송이의 측정값(150행 4열)이고 `iris.feature_names` 는 그 열 이름 4개입니다. `df['target'] = iris.target` 이 품종 열을 추가합니다.
- `train_test_split` 은 값 4개를 `훈련 데이터, 시험 데이터, 훈련 레이블, 시험 레이블` 순서로 돌려줍니다. 데이터 두 개가 먼저, 레이블 두 개가 나중입니다.
- 학습에는 훈련용만, 예측에는 시험 데이터만 씁니다. 정답률은 시험 레이블과 예측 결과를 비교합니다.
- `svm` 은 서포트 벡터 머신(Support Vector Machine), `SVC` 는 서포트 벡터 분류(Support Vector Classification)입니다. 데이터 집합에서 최대 마진을 가진 최적의 선(평면)을 찾아 분류합니다.
- `metrics` 는 성능 지표를 모아 둔 모듈이고 `accuracy_score()` 가 정답률을 계산합니다.
- 붓꽃 데이터는 150건입니다. 강의 결과의 `0.9473684210526315` 는 시험 데이터 38건 가운데 36건을 맞힌 값(36 / 38)입니다. 데이터를 무작위로 나누기 때문에 실행할 때마다 정답률이 달라질 수 있습니다.
- `iris.target` 은 품종을 0, 1, 2 로 적은 값이고 `iris.target_names` 는 순서대로 `setosa`, `versicolor`, `virginica` 입니다. 강의는 딕셔너리 `{0: 'setosa', 1: 'versicolor', 2: 'virginica'}` 를 만들어 `df['target'].map(target_names)` 로 숫자를 품종 이름으로 바꿨습니다. 슬라이드의 실행 결과에는 `target` 이 0 으로 적혀 있지만, `map` 까지 실행한 뒤의 `df.head()` 에는 `setosa` 가 나옵니다.

차시 과제에는 로지스틱 회귀 모델이 나왔습니다. 클래스만 바뀌고 `fit` 다음에 `predict` 를 부르는 순서는 같습니다.

```python
from sklearn.linear_model import LogisticRegression

X = [[1], [2], [3], [4], [5], [6], [7], [8], [9], [10]]
y = [0, 0, 0, 0, 1, 1, 1, 1, 1, 1]

model = LogisticRegression()
model.fit(X, y)
print(model.predict([[2], [9]]))            # [0 1]
```

## 7. SciPy 의 주요 모듈

| 서브모듈 | 분야 | 강의에 나온 함수 |
|---|---|---|
| `scipy.linalg` | 선형대수 | `solve(A, b)` |
| `scipy.optimize` | 최적화 | `minimize(f, x0=0)`, `root(equation, x0=1)` |
| `scipy.stats` | 통계 | `describe(data)` |
| `scipy.integrate` | 적분 | (이름만 소개) |
| `scipy.sparse` | 희소 행렬 | `csr_matrix(data)` |

```python
from scipy.linalg import solve

# 3x + 1y = 9
# 1x + 2y = 8
A = [[3, 1], [1, 2]]             # 계수를 한 식에 한 행씩
b = [9, 8]                       # 등호 오른쪽 값
x = solve(A, b)
print(f"Solution: {x}")          # Solution: [2. 3.]
```

```python
from scipy.optimize import minimize, root

def f(x):
    return x**2 + 4*x + 4        # (x + 2)² 이라 x = -2 에서 가장 작음

result = minimize(f, x0=0)       # x0 은 x 의 시작값
print(f"Optimal value: {result.x}")   # -2 에 가까운 값

def equation(x):
    return x**2 - 4              # x² - 4 = 0 의 왼쪽 식

sol = root(equation, x0=1)
print(f"Root: {sol.x}")          # Root: [2.]
```

```python
from scipy.stats import describe

data = [1, 2, 3, 4, 5, 6, 7]
print(describe(data))
# nobs=7, minmax=(1, 7), mean=4.0, variance=4.666666666666667, skewness=0.0, kurtosis=-1.25
```

```python
from scipy.sparse import csr_matrix

data = [
    [0, 0, 3],
    [4, 0, 0],
    [0, 5, 0]
]
print(csr_matrix(data))
#   (0, 2)    3
#   (1, 0)    4
#   (2, 1)    5
```

- `solve(A, b)` 는 `Ax = b` 꼴의 연립방정식을 풉니다. 결과는 실수 배열이라 `[2. 3.]` 처럼 점이 붙습니다.
- `minimize` 는 함수 값을 가장 작게 만드는 x 를 찾습니다. `result.x` 는 그때의 x 이고 함수의 최솟값이 아닙니다. 위 예에서 최솟값은 0, `result.x` 는 약 -2 입니다.
- `root` 는 함수 값이 0 이 되는 x(방정식의 근)를 찾습니다. 함수는 `= 0` 을 뺀 왼쪽 식만 `return` 합니다. `x² - 4 = 0` 의 근은 2 와 -2 이고 시작값 `x0=1` 에서 가까운 2 가 나옵니다.
- 과제의 `(x - 3)² = 0` 은 근이 3, `x² + 6x + 9 = 0` 은 `(x + 3)² = 0` 이라 근이 -3 입니다. 수치 계산이라 `-2.99999995` 처럼 근삿값으로 출력될 수 있습니다.
- `describe` 는 개수(`nobs`), 최솟값과 최댓값(`minmax`), 평균(`mean`), 분산(`variance`), 왜도(`skewness`), 첨도(`kurtosis`)를 한 번에 계산합니다. 중앙값은 들어 있지 않습니다. 강의 자료에는 왜도가 "외도"로 적혀 있습니다.
- 과제의 그룹 A `[80, 85, 90, 75, 95]` 는 `nobs=5`, `minmax=(75, 95)`, `mean=85.0`, `variance=62.5` 입니다. 분산은 편차 제곱의 합 250 을 n - 1 인 4 로 나눈 값입니다.
- `csr_matrix` 는 0 이 많은 2차원 데이터에서 0 이 아닌 요소만 `(행, 열) 값` 으로 보여 줍니다. 행과 열 번호는 0 부터 셉니다.
- 버전에 따라 `describe` 의 결과가 `mean=np.float64(4.0)` 처럼 자료형 이름과 함께 출력되지만 값은 `mean=4.0` 일 때와 같습니다.

## 시험에서 헷갈리기 쉬운 점

- 선형 회귀 모델 클래스는 대문자 `OLS` 입니다. `sm.ols`, `sm.LinearRegression` 은 없습니다.
- `sm.OLS(y, X)` 는 종속 변수가 먼저이고, scikit-learn 의 `fit(X, y)` 는 데이터가 먼저입니다.
- `sm.add_constant(X)` 의 결과를 다시 `X` 에 담아야 상수항이 들어갑니다. 함수 이름은 `add_constant` 이고 `add_intercept` 가 아닙니다.
- `sm.OLS(y, X)` 뒤에 `.fit()` 을 붙여야 학습이 됩니다. `summary()` 와 `params` 는 `fit()` 의 결과에 있습니다.
- `model.params` 는 `[절편, 기울기]` 순서입니다. 기울기는 `params[1]` 입니다.
- 결과 표에서 `const` 행의 `coef` 는 절편, 변수 이름 행의 `coef` 는 기울기입니다. 기울기가 음수이면 x 가 늘 때 예측값이 줄어듭니다.
- `R-squared` 는 1 에 가까울수록, `AIC` · `BIC` · `std err` 는 작을수록 좋습니다. `P>|t|` 와 `Prob (F-statistic)` 은 0.05 가 판단선입니다.
- `Df Model` 은 독립변수의 개수이고 상수항은 세지 않습니다.
- 다중 회귀에서 열을 여러 개 고를 때는 `data[['hp', 'wt']]` 로 씁니다. `data['hp', 'wt']` 는 `KeyError` 가 납니다.
- scikit-learn 은 `pip install scikit-learn` 으로 설치하고 `sklearn` 으로 임포트합니다.
- `train_test_split` 이 돌려주는 순서는 `train_data, test_data, train_label, test_label` 입니다. `train_data, train_label, …` 순서로 받으면 레이블 자리에 시험 데이터가 들어가 `fit` 에서 오류가 납니다.
- `fit(train_data, train_label)`, `predict(test_data)`, `accuracy_score(test_label, pre)` 의 인자를 구분합니다. 시험 데이터로 학습하거나 훈련 레이블로 채점하지 않습니다.
- 함수와 모듈의 짝: `load_iris` 는 `sklearn.datasets`, `train_test_split` 은 `sklearn.model_selection`, `SVC` 는 `sklearn.svm`, `accuracy_score` 는 `sklearn.metrics` 에 있습니다.
- `SVC` 는 분류 클래스입니다. `svm` 은 모듈 이름이라 `svm.SVC()` 로 모델을 만듭니다.
- 강의의 "150종류 이상"은 붓꽃 전체의 품종 수를 말합니다. 예제 데이터에는 setosa, versicolor, virginica 세 품종이 50건씩 모두 150건 들어 있습니다.
- 정답률은 0 과 1 사이의 실수라서 전부 맞혀도 `100` 이 아니라 `1.0` 이 출력됩니다.
- NumPy 배열은 `[1 0]` 처럼 쉼표 없이 출력됩니다. `[1, 0]` 은 리스트의 출력입니다.
- SciPy 서브모듈 이름: 선형대수 `linalg`, 최적화 `optimize`, 통계 `stats`, 적분 `integrate`, 희소 행렬 `sparse`. `minimize` 와 `root` 는 둘 다 `scipy.optimize` 에 있고, `optimize` 는 모듈 이름이지 함수가 아닙니다.
- 파이썬의 거듭제곱은 `**` 입니다. 슬라이드 주석의 `x^2` 를 코드에 그대로 쓰면 거듭제곱이 되지 않고, `6x` 처럼 곱셈 기호를 빼면 문법 오류입니다. `x**2 + 6*x + 9` 로 씁니다.
- `minimize` 의 `x0` 은 답이 아니라 탐색을 시작하는 값입니다.
- `solve(A, b)` 의 `A` 는 식 하나의 계수가 한 행입니다. `[[3, 1], [1, 2]]` 는 `3x + y` 와 `x + 2y` 입니다.
- `csr_matrix` 출력의 좌표는 `(행, 열)` 순서이고 0 부터 셉니다. 둘째 행 첫째 열은 `(1, 0)` 입니다.
