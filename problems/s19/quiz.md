# 19차시 퀴즈: statsmodels·scikit-learn·SciPy

> 코드를 실행하지 말고 눈으로 풀어 보세요. 답은 `submissions/<내 ID>/s19/quiz.py` 에 적습니다.

## Q1 (객관식 · 2점)

`import statsmodels.api as sm` 으로 불러온 statsmodels 에서 선형 회귀 모델을 생성할 때 쓰는 클래스는?

1. `sm.LinearRegression`
2. `sm.ols`
3. `sm.OLS`
4. `sm.RegressionModel`

## Q2 (객관식 · 2점)

statsmodels 에서 독립 변수에 상수항(절편)을 추가하는 함수는?

1. `sm.add_constant()`
2. `sm.add_intercept()`
3. `sm.include_constant()`
4. `sm.set_constant()`

## Q3 (객관식 · 2점)

scikit-learn 에서 데이터를 훈련용과 시험용으로 나누는 함수는?

1. `split_data()`
2. `data_split()`
3. `divide()`
4. `train_test_split()`

## Q4 (객관식 · 2점)

강의의 XOR 학습과 붓꽃 분류에서 모델을 만들 때 쓴, scikit-learn 의 서포트 벡터 머신 분류 클래스는?

1. `svm.SupportVector()`
2. `svm.SVC()`
3. `svm.SVMClassifier()`
4. `svm.SVR()`

## Q5 (객관식 · 2점)

SciPy 에서 함수의 값을 가장 작게 만드는 변수 값을 구하는 최적화 함수는?

1. `minimize()`
2. `optimize()`
3. `fit()`
4. `gradient()`

## Q6 (객관식 · 2점)

SciPy 의 서브모듈과 그 모듈이 다루는 분야의 짝으로 옳지 **않은** 것은?

1. `scipy.sparse` 는 통계
2. `scipy.linalg` 는 선형대수
3. `scipy.optimize` 는 최적화
4. `scipy.integrate` 는 적분

## Q7 (객관식 · 2점)

선형 회귀에 대한 설명으로 옳지 **않은** 것은?

1. 독립 변수와 종속 변수 사이의 선형 관계를 모델링하는 기법이다.
2. 가설을 `H(x) = Wx + b` 로 나타내며 `W` 는 기울기, `b` 는 y 절편이다.
3. 데이터에 가장 가까운 직선이 되도록 `W` 와 `b` 를 찾는 것이 학습이다.
4. 종속 변수는 다른 것의 영향을 받지 않는 변수이고, 독립 변수는 종속 변수에 따라 값이 변하는 변수이다.

## Q8 (단답 · 3점)

학습을 마친 선형 회귀 모델 `model` 의 결과를 요약한 표(OLS Regression Results)를 출력하려고 합니다. 빈칸(`____`)에 들어갈 메서드 이름을 적으세요.

```python
model = sm.OLS(y, X).fit()
print(model.____())
```

## Q9 (객관식 · 2점)

세 패키지에 대한 설명으로 옳지 **않은** 것은?

1. statsmodels 는 선형 회귀와 로지스틱 회귀 분석, ARIMA 모델을 포함한 시계열 분석, 가설 검정 같은 통계적 테스트 기능을 제공하고, 강의에서는 `import statsmodels.api as sm` 으로 불러왔다.
2. scikit-learn 은 파이썬 기반의 머신러닝 라이브러리이고, `pip install scikit-learn` 으로 설치한 뒤 `import scikit-learn as sk` 로 불러온다.
3. scikit-learn 의 모델은 종류가 달라도 `fit(X, y)`, `predict(X)`, `score(X, y)` 같은 공통 메서드를 쓴다.
4. SciPy 는 과학 및 공학 계산 라이브러리이고 NumPy 위에 구축되어 있다.

## Q10 (단답 · 3점)

다음은 scikit-learn 의 로지스틱 회귀 모델을 학습시킨 뒤 새로운 입력의 결과를 예측하는 코드입니다. 빈칸(`____`)에 들어갈 메서드 이름을 적으세요. `svm.SVC()` 로 만든 모델을 학습시킬 때 쓰는 메서드와 이름이 같습니다.

```python
from sklearn.linear_model import LogisticRegression

X = [[1], [2], [3], [4], [5], [6], [7], [8], [9], [10]]
y = [0, 0, 0, 0, 1, 1, 1, 1, 1, 1]

model = LogisticRegression()
model.____(X, y)
print(model.predict([[4.5], [6.5]]))
```

## Q11 (객관식 · 2점)

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

## Q12 (객관식 · 2점)

다음은 `hp`(마력)로 `mpg`(연비)를 예측한 선형 회귀 요약표의 일부입니다. 이 표의 회귀식으로 계산할 때, 마력이 100 인 자동차의 예측 연비에 가장 가까운 값은?

```text
              coef    std err        t      P>|t|
const      30.0989      1.634   18.421      0.000
hp         -0.0682      0.010   -6.742      0.000
```

1. 약 23.28
2. 약 30.03
3. 약 36.92
4. 약 3009.82

## Q13 (객관식 · 2점)

다음 선형 회귀 요약표에서 읽을 수 있는 내용으로 옳지 **않은** 것은?

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

1. 표본은 32개이고 독립변수는 1개이다.
2. 독립변수 `hp` 가 종속변수 `mpg` 의 약 60% 를 설명한다.
3. `hp` 의 `P>|t|` 가 0.05 보다 작으므로 `hp` 의 영향은 통계적으로 유의미하다고 본다.
4. `hp` 가 1 늘어날 때마다 `mpg` 가 약 30.1 씩 늘어난다.
5. 다른 모델과 비교할 때 `AIC` 와 `BIC` 는 값이 낮은 쪽을 더 좋은 모델로 본다.

## Q14 (객관식 · 2점)

다음 코드에서 모델이 XOR 연산을 올바르게 학습했다면 출력되는 것은?

```python
from sklearn import svm
from sklearn import metrics

clf = svm.SVC()
clf.fit([[0, 0], [0, 1], [1, 0], [1, 1]], [0, 1, 1, 0])

pre = clf.predict([[0, 0], [0, 1], [1, 0], [1, 1]])
print(pre)
ac_score = metrics.accuracy_score([0, 1, 1, 1], pre)
print(f"정답률: {ac_score}")
```

**1번**

```
[0 1 1 0]
정답률: 1.0
```

**2번**

```
[0, 1, 1, 1]
정답률: 75
```

**3번**

```
[0 1 1 0]
정답률: 0.75
```

**4번**

```
[0 1 1 1]
정답률: 1.0
```

## Q15 (객관식 · 2점)

붓꽃 데이터를 훈련용(`train_data`, `train_label`)과 시험용(`test_data`, `test_label`)으로 나누어 두었습니다. 훈련용으로 학습하고 시험용으로 정답률을 구하려고 할 때, (가), (나), (다)에 들어갈 것을 옳게 짝지은 것은?

```python
from sklearn import svm, metrics

clf = svm.SVC()
clf.fit((가))
pre = clf.predict((나))
ac_score = metrics.accuracy_score((다), pre)
print("정답률 =", ac_score)
```

1. (가) `train_data, test_data` (나) `train_label` (다) `test_label`
2. (가) `train_data, train_label` (나) `test_data` (다) `test_label`
3. (가) `test_data, test_label` (나) `train_data` (다) `train_label`
4. (가) `train_data, train_label` (나) `test_label` (다) `test_data`

## Q16 (객관식 · 2점)

붓꽃 분류 예제에서 쓴 함수·클래스와 그것이 들어 있는 모듈의 짝으로 옳지 **않은** 것은?

1. `load_iris` 는 `sklearn.datasets` 에 들어 있다.
2. `train_test_split` 은 `sklearn.model_selection` 에 들어 있다.
3. `SVC` 는 `sklearn.svm` 에 들어 있다.
4. `accuracy_score` 는 `sklearn.model_selection` 에 들어 있다.

## Q17 (객관식 · 2점)

다음은 SciPy 로 방정식 x² + 6x + 9 = 0 의 근을 찾는 프로그램입니다. (가)에 들어갈 식과 출력되는 근을 옳게 짝지은 것은?

```python
from scipy.optimize import root

def equation(x):
    return (가)

sol = root(equation, x0=0)
print(f"Root: {sol.x}")
```

1. (가)는 `x**2 + 6*x + 9` 이고 근은 3 에 가까운 값이다.
2. (가)는 `x^2 + 6x + 9` 이고 근은 -3 에 가까운 값이다.
3. (가)는 `x**2 + 6*x + 9 == 0` 이고 근은 -3 에 가까운 값이다.
4. (가)는 `x**2 + 6*x + 9` 이고 근은 -3 에 가까운 값이다.

## Q18 (객관식 · 2점)

다음 코드가 푸는 연립방정식과 출력을 옳게 짝지은 것은?

```python
from scipy.linalg import solve

A = [[1, 2], [3, 4]]
b = [5, 11]
x = solve(A, b)
print(f"Solution: {x}")
```

1. `x + 3y = 5`, `2x + 4y = 11` 을 풀어 `Solution: [1. 2.]` 를 출력한다.
2. `x + 2y = 5`, `3x + 4y = 11` 을 풀어 `Solution: [1. 2.]` 를 출력한다.
3. `x + 2y = 5`, `3x + 4y = 11` 을 풀어 `Solution: [2. 1.]` 을 출력한다.
4. `x + 2y = 3`, `4x + 5y = 11` 을 풀어 `Solution: [5. 11.]` 을 출력한다.

## Q19 (객관식 · 2점)

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

## Q20 (단답 · 3점)

다음은 statsmodels 로 선형 회귀를 적용해 기울기를 출력하는 프로그램입니다. `< 1 >` 에는 상수항을 추가하는 함수의 이름이 들어갑니다. `< 2 >` 에 들어갈 속성 이름을 적으세요. 이 속성에는 회귀 계수가 절편, 기울기 순서로 들어 있습니다.

```python
import numpy as np
import statsmodels.api as sm

X = np.array([1, 2, 3, 4, 5])
y = np.array([2, 4, 5, 4, 5])

X = sm.< 1 >(X)

model = sm.OLS(y, X).fit()

W = model.< 2 >[1]

print("기울기 (coef):", W)
```

## Q21 (객관식 · 2점)

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

## Q22 (객관식 · 2점)

다음은 statsmodels 로 선형 회귀를 적용하는 프로그램입니다. 빈칸 `< 1 >`, `< 2 >` 를 알맞게 채워 실행했을 때의 출력에 가장 가까운 것은? 실수 계산이라 실제 출력에는 소수 끝자리가 더 붙을 수 있습니다.

```python
import numpy as np
import statsmodels.api as sm

X = np.array([1, 2, 3, 4, 5])
y = np.array([2, 4, 5, 4, 5])

X = sm.< 1 >(X)

model = sm.OLS(y, X).fit()

W = model.< 2 >[1]

print("기울기 (coef):", W)
```

1. `기울기 (coef): 4.0`
2. `기울기 (coef): 2.2`
3. `기울기 (coef): 1.2`
4. `기울기 (coef): 0.6`

## Q23 (객관식 · 2점)

선형 회귀로 구한 기울기 `W` 와 절편 `b` 로 그래프를 그리려고 합니다. 데이터는 점으로 찍고 회귀 직선은 빨간 선으로 그릴 때, (가)와 (나)에 들어갈 코드로 옳은 것은?

```python
import numpy as np
import matplotlib.pyplot as plt

x = np.array([1, 2, 3, 4, 5])
y = np.array([2, 4, 6, 8, 10])
W = 2.0    # 선형 회귀로 구한 기울기
b = 0.0    # 선형 회귀로 구한 절편

(가)
(나)
plt.title("Linear Regression")
plt.xlabel("x")
plt.ylabel("y")
plt.show()
```

1. (가) `plt.plot(x, y)` (나) `plt.scatter(x, W * x + b, color="red")`
2. (가) `plt.scatter(x, y)` (나) `plt.plot(x, W * x + b, color="red")`
3. (가) `plt.scatter(x, y)` (나) `plt.plot(x, b * x + W, color="red")`
4. (가) `plt.bar(x, y)` (나) `plt.hist(W * x + b, color="red")`

## Q24 (객관식 · 2점)

`iris_data` 는 붓꽃 150송이의 크기를 담은 4열짜리 데이터프레임이고 `iris_label` 은 품종을 담은 열입니다. 다음 코드를 실행하면 `clf.fit(...)` 줄에서 오류가 납니다. 원인으로 옳은 것은?

```python
from sklearn.model_selection import train_test_split
from sklearn import svm

train_data, train_label, test_data, test_label = \
    train_test_split(iris_data, iris_label)

clf = svm.SVC()
clf.fit(train_data, train_label)
```

1. `train_test_split` 은 값을 2개만 돌려주므로 변수 4개로 받을 수 없다.
2. `fit` 에는 레이블을 먼저, 데이터를 나중에 넘겨야 한다.
3. `train_test_split` 은 훈련 데이터, 시험 데이터, 훈련 레이블, 시험 레이블 순서로 돌려주므로 `train_label` 에 시험 데이터가 들어갔다.
4. `svm.SVC()` 로 만든 모델은 `fit` 이 아니라 `train` 메서드로 학습한다.

## Q25 (객관식 · 2점)

다음 코드에서 `data` 와 `label` 에 담기는 것을 옳게 설명한 것은?

```python
import pandas as pd

xor_data = [
    # P, Q, result
    [0, 0, 0],
    [0, 1, 1],
    [1, 0, 1],
    [1, 1, 0]
]
xor_df = pd.DataFrame(xor_data)
data = xor_df.loc[:, 0:1]
label = xor_df.loc[:, 2]
```

1. `data` 는 P 와 Q 두 열(0번, 1번 열)이고 `label` 은 result 열(2번 열)이다.
2. `data` 는 P 열 하나(0번 열)이고 `label` 은 result 열(2번 열)이다.
3. `data` 는 처음 두 행(0번, 1번 행)이고 `label` 은 2번 행이다.
4. `data` 는 세 열 전체이고 `label` 은 Q 열(1번 열)이다.

## Q26 (객관식 · 2점)

다음 코드에서 `result.x` 에 가장 가까운 값은?

```python
from scipy.optimize import minimize

def f(x):
    return x**2 - 6*x + 10

result = minimize(f, x0=0)
print(f"Optimal value: {result.x}")
```

1. 0 에 가까운 값
2. 1 에 가까운 값
3. 3 에 가까운 값
4. 10 에 가까운 값

## Q27 (객관식 · 2점)

다음 코드의 출력에 표시되는 좌표(Coords)와 값(Values)을 옳게 나열한 것은?

```python
from scipy.sparse import csr_matrix

data = [
    [0, 7, 0],
    [0, 0, 0],
    [2, 0, 9]
]
sparse_matrix = csr_matrix(data)
print(sparse_matrix)
```

1. `(1, 0) 7`, `(0, 2) 2`, `(2, 2) 9`
2. `(0, 1) 7`, `(2, 0) 2`, `(2, 2) 9`
3. `(1, 2) 7`, `(3, 1) 2`, `(3, 3) 9`
4. `(0, 0) 0` 부터 `(2, 2) 9` 까지 9개가 모두 표시된다.

## Q28 (객관식 · 2점)

선형 회귀 요약표(OLS Regression Results)의 항목에 대한 설명으로 옳지 **않은** 것은?

1. `R-squared` 는 결정 계수이고 0 에서 1 사이의 값이며, 1 에 가까울수록 모델이 데이터를 잘 설명한다.
2. `Adj. R-squared` 는 독립변수가 늘면 결정 계수가 커지는 문제를 독립변수의 개수와 표본 크기로 조정한 값이다.
3. `F-statistic` 은 회귀모델 전체가 통계적으로 유의한지 보는 값이고, 값이 작을수록 유의하다고 판단한다.
4. `std err` 는 계수 추정치의 표준오차이고 값이 작을수록 좋다.

## Q29 (객관식 · 2점)

`mtcars` 는 자동차 32종의 데이터입니다. 마력(`hp`)과 중량(`wt`) 두 열을 독립변수로, 연비(`mpg`)를 종속변수로 두고 상수항을 추가해 다중 선형 회귀를 학습했습니다. 요약표의 `No. Observations`, `Df Model`, `Df Residuals` 값을 순서대로 옳게 적은 것은?

1. 32, 2, 29
2. 32, 2, 30
3. 32, 3, 29
4. 30, 2, 28

## Q30 (단답 · 3점)

다음은 XOR 연산을 학습한 모델로 새 데이터의 답을 예측하는 코드입니다. 빈칸(`____`)에 들어갈 메서드 이름을 적으세요.

```python
from sklearn import svm

clf = svm.SVC()
clf.fit([[0, 0], [0, 1], [1, 0], [1, 1]], [0, 1, 1, 0])

pre = clf.____([[0, 1], [1, 1]])
print(pre)    # [1 0]
```

## Q31 (단답 · 3점)

`data` 는 XOR 연산의 입력 4건이고 `label` 은 그 정답입니다. 다음은 모델의 예측 결과 `pre` 를 정답과 비교해 정답률을 구하는 코드입니다. 빈칸(`____`)에 들어갈 함수 이름을 적으세요.

```python
from sklearn import svm, metrics

clf = svm.SVC()
clf.fit(data, label)
pre = clf.predict(data)

ac_score = metrics.____(label, pre)
print(f"정답률= {ac_score}")
```

## Q32 (단답 · 3점)

다음은 SciPy 로 방정식 (x - 3)² = 0 의 근을 구하는 프로그램입니다. 빈칸(`____`) 두 곳에는 같은 함수 이름이 들어갑니다. 그 이름을 적으세요.

```python
from scipy.optimize import ____

def equation(x):
    return (x - 3)**2

sol = ____(equation, x0=0)
print(f"Root: {sol.x}")
```

## Q33 (단답 · 3점)

다음은 SciPy 로 연립방정식 `3x + y = 9`, `x + 2y = 8` 을 푸는 프로그램입니다. 빈칸(`____`) 두 곳에는 같은 함수 이름이 들어갑니다. 그 이름을 적으세요.

```python
from scipy.linalg import ____

A = [[3, 1], [1, 2]]
b = [9, 8]
x = ____(A, b)
print(f"Solution: {x}")    # Solution: [2. 3.]
```

## Q34 (객관식 · 2점)

다음은 붓꽃 데이터를 불러와 데이터프레임으로 만드는 코드입니다. 설명으로 옳지 **않은** 것은?

```python
from sklearn.datasets import load_iris
import pandas as pd

iris = load_iris()
df = pd.DataFrame(data=iris.data, columns=iris.feature_names)
df['target'] = iris.target
print(df.head())
```

1. `iris.data` 에는 꽃받침과 꽃잎의 길이와 너비를 잰 값이 들어 있다.
2. `iris.feature_names` 는 `sepal length (cm)` 같은 이름 4개이고 `df` 의 열 이름이 된다.
3. `df['target'] = iris.target` 은 `df` 에 `target` 열을 추가한다.
4. `iris.target` 에는 품종이 `'setosa'` 같은 문자열로 들어 있어서 출력의 `target` 열에 품종 이름이 나온다.

## Q35 (객관식 · 2점)

강의에서 소개한 statsmodels 의 주요 기능이 **아닌** 것은?

1. 선형 회귀 및 로지스틱 회귀 분석
2. ARIMA 모델을 포함한 시계열 분석
3. 가설 검정, 모델 선택, 변수 선택을 위한 통계적 테스트
4. 0 이 많은 2차원 데이터를 0 이 아닌 요소만 표시하는 희소 행렬로 변환

## Q36 (객관식 · 2점)

강의에 나온 이름과 그 설명의 짝으로 옳지 **않은** 것은?

1. `OLS` 는 Ordinary Least Squares 의 줄임말이고, 오차의 제곱을 최소화하는 기울기와 절편을 추정하는 방식이다.
2. `SVC` 는 서포트 벡터 분류(Support Vector Classification)이고, 최대 마진을 가진 최적의 선(평면)을 찾아 데이터를 분류한다.
3. `metrics` 는 성능 지표를 모아 둔 모듈이고, `accuracy_score()` 가 정답률을 계산한다.
4. `fit()` 은 시험 데이터에 대해 분류를 수행하고, `predict()` 는 훈련 데이터에 따라 모델을 피팅한다.

## Q37 (객관식 · 2점)

배타적 논리합(XOR)에 대한 설명으로 옳은 것은?

1. 두 입력이 모두 참일 때만 참이다.
2. 두 입력 가운데 하나라도 참이면 참이다.
3. 두 입력 가운데 하나만 참일 때 참이고, 둘 다 참이거나 둘 다 거짓이면 거짓이다.
4. 두 입력이 서로 같을 때 참이고, 서로 다르면 거짓이다.

## Q38 (객관식 · 2점)

선형 회귀 요약표(OLS Regression Results)의 항목에 대한 설명으로 옳지 **않은** 것은?

1. `BIC` 는 AIC 보다 모델의 복잡도에 더 작은 벌점을 주어 더 복잡한 모델을 선호하고, 값이 클수록 좋은 모델이다.
2. `t` 는 회귀계수가 0 이라는 가설에서 그 계수가 표준오차에 비해 얼마나 큰지 나타내는 값이고, 절댓값이 클수록 그 변수의 영향이 통계적으로 뚜렷하다.
3. `P>|t|` 는 회귀계수가 0 이라는 가설에서 지금과 같은 t 값이 나올 확률이고, 0.05 보다 작으면 통계적으로 유의미하다고 본다.
4. `Prob (F-statistic)` 은 F 통계량의 p 값이고, 0.05 이하이면 회귀모델 전체가 통계적으로 유의미하다고 본다.

## Q39 (객관식 · 2점)

다음은 SciPy 로 방정식 x² - 4 = 0 의 근을 찾는 프로그램입니다. 출력에 가장 가까운 것은?

```python
from scipy.optimize import root

def equation(x):
    return x**2 - 4

sol = root(equation, x0=1)
print(f"Root: {sol.x}")
```

1. `Root: [-2.]`
2. `Root: [2.]`
3. `Root: [ 2. -2.]`
4. `Root: [1.]`

## Q40 (객관식 · 2점)

시험공부를 5시간 한 학생이 50점, 10시간 한 학생이 100점을 받았습니다. 이 관계를 선형 회귀의 가설 `H(x) = Wx + b` 로 나타내고 7시간 공부한 학생의 점수를 예측할 때, `W`, `b`, 예측 점수를 옳게 짝지은 것은?

1. `W` 는 50, `b` 는 0, 예측 점수는 350점
2. `W` 는 10, `b` 는 50, 예측 점수는 120점
3. `W` 는 10, `b` 는 0, 예측 점수는 70점
4. `W` 는 0, `b` 는 10, 예측 점수는 10점

## Q41 (객관식 · 2점)

강의에서 설명한 scikit-learn 과 SciPy 의 특징으로 옳지 **않은** 것은?

1. scikit-learn 은 분류, 회귀, 클러스터링 같은 여러 알고리즘을 지원한다.
2. scikit-learn 은 NumPy 배열, pandas 데이터프레임 같은 표준화된 데이터 구조로 입력과 출력을 주고받는다.
3. NumPy 는 고급 수학 및 과학 계산 기능을 제공하고, SciPy 는 다차원 배열과 기본 연산을 제공한다.
4. SciPy 는 NumPy 와 함께 쓰여 데이터 분석과 수학적 계산에 알맞다.
