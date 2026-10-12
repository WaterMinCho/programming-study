# 18차시 퀴즈: Pandas·NumPy·Matplotlib

> 코드를 실행하지 말고 눈으로 풀어 보세요. 답은 `submissions/<내 ID>/s18/quiz.py` 에 적습니다.

## Q1 (객관식 · 2점)

Pandas 에서 데이터프레임(DataFrame)을 생성하는 데 사용하는 함수는?

1. `pd.Series()`
2. `pd.DataFrame()`
3. `pd.Array()`
4. `pd.Table()`

## Q2 (객관식 · 2점)

pandas 와 패키지 설치에 대한 설명으로 옳지 **않은** 것은?

1. Series 는 라벨이 있는 1차원 자료구조이고, DataFrame 은 행과 열에 라벨이 있는 2차원 테이블 구조이다.
2. CSV 는 Comma Separated Values 의 줄임말로, 데이터를 쉼표로 구분한 파일이다.
3. pandas 는 파이썬 표준 모듈이 아니므로 `pip install pandas` 로 설치한 뒤 `import pandas as pd` 로 불러온다.
4. `pip list` 는 설치된 패키지를 제거하는 명령이다.

## Q3 (객관식 · 2점)

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

## Q4 (객관식 · 2점)

`print(df)` 의 결과가 아래와 같은 DataFrame `df` 를 만드는 코드를 **모두 고르세요**. 네 코드 모두 `import pandas as pd` 를 먼저 실행했다고 봅니다.

```
   ID   Name  Age
0   1  Alice   30
1   2    Bob   35
```

**1번**

```python
data = [[1, 'Alice', 30], [2, 'Bob', 35]]
df = pd.DataFrame(data, columns=['ID', 'Name', 'Age'])
```

**2번**

```python
data = {'ID': [1, 2], 'Name': ['Alice', 'Bob'], 'Age': [30, 35]}
df = pd.DataFrame(data)
```

**3번**

```python
data = [[1, 2], ['Alice', 'Bob'], [30, 35]]
df = pd.DataFrame(data, columns=['ID', 'Name', 'Age'])
```

**4번**

```python
data = {'ID': [1, 2], 'Name': ['Alice', 'Bob'], 'Age': [30, 35]}
df = pd.Series(data)
```

## Q5 (객관식 · 2점)

Pandas 에서 데이터프레임의 첫 몇 줄을 출력할 때 사용하는 메서드는?

1. `head()`
2. `tail()`
3. `summary()`
4. `info()`

## Q6 (객관식 · 2점)

`df` 는 행이 6개인 DataFrame 입니다. 데이터를 불러오고 살펴보는 방법에 대한 설명으로 옳지 **않은** 것은?

1. `pd.read_excel()` 로 엑셀 파일을 읽으려면 openpyxl 모듈을 따로 설치해야 한다.
2. `df.tail()` 은 마지막 5개 행을 보여 준다.
3. `df.describe()` 는 숫자 열마다 count, mean, std, min, 25%, 50%, 75%, max 를 보여 준다.
4. `df.sample(frac=0.5)` 는 맨 앞에서부터 3개 행을 순서대로 돌려준다.

## Q7 (단답 · 3점)

`data.csv` 파일의 내용이 아래와 같습니다.

```
Name,Age,Salary
Alice,25,50000
Bob,30,60000
Carol,28,55000
Dave,35,70000
```

이 파일을 DataFrame 으로 불러와 열마다 평균, 최댓값, 최솟값을 출력하려고 합니다. 빈칸(`____`)에 들어갈 함수 이름을 적으세요.

```python
import pandas as pd

df = pd.____('data.csv')
for col in ['Age', 'Salary']:
    print(f"{col} 평균: {df[col].mean()}, 최댓값: {df[col].max()}, 최솟값: {df[col].min()}")
```

출력 결과는 아래와 같습니다.

```
Age 평균: 29.5, 최댓값: 35, 최솟값: 25
Salary 평균: 58750.0, 최댓값: 70000, 최솟값: 50000
```

## Q8 (객관식 · 2점)

다음 코드를 실행했을 때 출력되는 것은?

```python
import pandas as pd

data = {'ID': [1, 2, 3], 'Name': ['Alice', 'Bob', 'Charlie'], 'Age': [25, 35, 30]}
df = pd.DataFrame(data)
filtered = df[df['Age'] > 25]
print(filtered)
```

**1번**

```
   ID     Name  Age
1   2      Bob   35
2   3  Charlie   30
```

**2번**

```
   ID     Name  Age
0   2      Bob   35
1   3  Charlie   30
```

**3번**

```
   ID     Name  Age
0   1    Alice   25
1   2      Bob   35
2   3  Charlie   30
```

**4번**

```
0    False
1     True
2     True
Name: Age, dtype: bool
```

## Q9 (객관식 · 2점)

다음 DataFrame 에서 30세 이상이면서 연봉(Salary)이 60000 이상인 사람만 골라 출력하려고 합니다.

```python
import pandas as pd

data = {
    'Name': ['Alice', 'Bob', 'Carol', 'Dave'],
    'Age': [25, 30, 28, 35],
    'Salary': [50000, 60000, 65000, 70000]
}
df = pd.DataFrame(data)
filtered = ____
print(filtered)
```

출력 결과가 아래와 같아지도록 빈칸(`____`)에 넣을 코드는?

```
   Name  Age  Salary
1   Bob   30   60000
3  Dave   35   70000
```

1. `df[df['Age'] >= 30 and df['Salary'] >= 60000]`
2. `df[(df['Age'] >= 30) & (df['Salary'] >= 60000)]`
3. `df[(df['Age'] >= 30) | (df['Salary'] >= 60000)]`
4. `df[(df['Age'] > 30) & (df['Salary'] > 60000)]`

## Q10 (객관식 · 2점)

다음 코드가 출력하는 표에서 맨 왼쪽에 나오는 인덱스를 위에서부터 순서대로 적은 것은?

```python
import pandas as pd

data = {'ID': [1, 2, 3], 'Name': ['Alice', 'Bob', 'Charlie'], 'Age': [30, 35, 25]}
df = pd.DataFrame(data)
df['Salary'] = [50000, 60000, 70000]
df.loc[len(df)] = [4, 'David', 40, 80000]
df = df.drop(1)
sorted_df = df.sort_values(by='Age')
print(sorted_df)
```

1. `0, 1, 2`
2. `0, 2, 3`
3. `2, 0, 3`
4. `2, 0, 1, 3`

## Q11 (객관식 · 2점)

다음 코드에 대한 설명으로 옳지 **않은** 것은?

```python
import pandas as pd

df = pd.DataFrame({'ID': [1, 2], 'Name': ['Alice', 'Bob'], 'Salary': [50000, 60000]})
df2 = pd.DataFrame({'ID': [3], 'Name': ['Eve']})
df3 = pd.DataFrame({'ID': [1, 3], 'Department': ['HR', 'Sales']})

concated = pd.concat([df, df2])
merged = pd.merge(concated, df3)
```

1. `pd.concat()` 에는 이어 붙일 DataFrame 들을 리스트로 묶어 넘긴다.
2. `concated` 는 3행이고, Eve 행의 `Salary` 는 NaN 이다.
3. `concated` 의 인덱스는 0, 1, 2 로 새로 매겨진다.
4. `merged` 는 `ID` 가 양쪽에 모두 있는 1, 3 인 행만 남아 2행이고, `Department` 열이 붙는다.

## Q12 (객관식 · 2점)

다음 코드에 대한 설명으로 옳지 **않은** 것은?

```python
import pandas as pd

df = pd.DataFrame({
    'Name': ['Alice', 'Charlie', 'David', 'Eve', 'Frank'],
    'Salary': [40000, 60000, 80000, None, None]
})
print(df.isnull().sum())
meanVal = df['Salary'].mean()
df['Salary'] = df['Salary'].fillna(meanVal)
print(df)
```

1. 첫 번째 `print` 에서 `Salary` 옆에는 결측치의 개수인 2 가 나온다.
2. `meanVal` 은 결측치를 0 으로 치고 5 로 나눈 36000.0 이다.
3. `fillna(meanVal)` 은 값이 NaN 인 자리만 `meanVal` 로 채운다.
4. 마지막 `print` 에서 Eve 와 Frank 의 `Salary` 는 같은 값으로 나온다.

## Q13 (단답 · 3점)

`df1.duplicated()` 는 앞에 나온 행과 내용이 모두 같은 행을 `True` 로 표시합니다. 이렇게 중복된 행을 제거한 DataFrame 을 돌려주는 메서드의 이름을 빈칸(`____`)에 맞게 적으세요.

```python
df1_1 = df1.____()
print(df1_1)
```

## Q14 (객관식 · 2점)

NumPy 에서 배열을 생성하는 함수는? 아래 코드의 빈칸(`____`)에 넣으면 `[1 2 3 4 5]` 가 출력됩니다.

```python
import numpy as np

arr = ____([1, 2, 3, 4, 5])
print(arr)
```

1. `np.list`
2. `np.array`
3. `np.Array`
4. `np.matrix`

## Q15 (객관식 · 2점)

NumPy 에서 `(3, 3)` 같은 모양을 넘기면 그 모양대로 모든 요소가 0 으로 초기화된 배열을 만드는 함수는?

1. `np.empty()`
2. `np.zeros_like()`
3. `np.zeros()`
4. `np.zeros_array()`

## Q16 (객관식 · 2점)

다음 코드와 NumPy 에 대한 설명으로 옳지 **않은** 것은?

```python
import numpy as np

arr = np.array([1, 2, 3, 4, 5])
```

1. NumPy 는 Numerical Python 을 줄인 이름으로 다차원 배열과 행렬 연산을 지원하고, pandas 를 설치하면 함께 설치된다.
2. `print(arr)` 는 쉼표 없이 `[1 2 3 4 5]` 를 출력하고, `arr.shape` 는 `(5,)` 이다.
3. `arr * 2` 는 리스트에 2 를 곱할 때처럼 요소가 10개인 `[1 2 3 4 5 1 2 3 4 5]` 가 된다.
4. `import pandas as pd` 를 한 뒤 `pd.DataFrame(arr, columns=['Value'])` 로 이 배열을 DataFrame 으로 바꿀 수 있다.

## Q17 (객관식 · 2점)

NumPy 배열을 만드는 함수에 대한 설명으로 옳지 **않은** 것은?

1. `np.zeros((3, 3))` 과 `np.ones((2, 4))` 는 각각 0 과 1 로 채운 배열이고, 출력하면 요소가 `0.`, `1.` 처럼 실수로 나온다.
2. `np.full((2, 2), 7)` 은 모든 요소가 7 인 2행 2열 배열이다.
3. `np.eye(2, 3)` 과 `np.identity(3)` 은 모든 요소가 1 인 배열이다.
4. `np.random.randint(1, 10, (3, 3))` 은 1 이상 10 미만의 정수 난수로 채운 3행 3열 배열이다.

## Q18 (객관식 · 2점)

다음 코드를 실행했을 때 출력되는 것은? `np.arange(1, 11)` 은 1부터 10까지의 정수가 들어 있는 배열을 만듭니다.

```python
import numpy as np

arr = np.arange(1, 11)
squared = arr ** 2
print(squared.mean(), squared.max(), squared.min())
```

1. `5.5 10 1`
2. `38.5 100 1`
3. `385 100 1`
4. `38.5 10 1`

## Q19 (객관식 · 2점)

다음 코드를 실행했을 때 출력되는 것은?

```python
import numpy as np

arr1 = np.array([1, 2, 3])
arr2 = np.array([[10], [20], [30]])
result = arr1 + arr2
print(result.shape, result[2])
```

1. `(3, 3) [31 32 33]`
2. `(3, 3) [13 23 33]`
3. `(3,) 33`
4. 두 배열의 모양이 달라 오류가 발생한다

## Q20 (단답 · 3점)

두 행렬의 행렬 곱을 구하려고 합니다. 빈칸(`____`)에 들어갈 함수 이름을 적으세요.

```python
import numpy as np

matrix1 = np.array([[1, 2], [3, 4]])
matrix2 = np.array([[5, 6], [7, 8]])
result = np.____(matrix1, matrix2)
print(result)
```

출력 결과는 아래와 같습니다. `matrix1 * matrix2` 로 계산하면 같은 자리의 요소끼리 곱해져 첫 줄이 `[ 5 12]` 가 되므로 이 결과와 다릅니다.

```
[[19 22]
 [43 50]]
```

## Q21 (객관식 · 2점)

다음 코드를 실행했을 때 출력되는 것은?

```python
import numpy as np

arr = np.array([[10, 20, 30], [40, 50, 60]])
print(arr[1, 0])
print(arr[:, 2])
print(arr[arr > 25])
```

**1번**

```
40
[30 60]
[30 40 50 60]
```

**2번**

```
20
[30 60]
[30 40 50 60]
```

**3번**

```
40
[40 50 60]
[30 40 50 60]
```

**4번**

```
40
[30 60]
[40 50 60]
```

## Q22 (객관식 · 2점)

NumPy 로 3행 4열 크기의 정수 난수 행렬 `arr` 을 만들어 출력했더니 아래와 같았습니다.

```
[[ 3 10  5  7]
 [ 6  8  2  1]
 [12  4 11  9]]
```

각 행(row)의 최댓값을 모은 `[10  8 12]` 를 출력하는 코드는?

1. `print(arr.max())`
2. `print(arr.max(axis=0))`
3. `print(arr.max(axis=1))`
4. `print(arr[:, 3])`

## Q23 (객관식 · 2점)

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

## Q24 (객관식 · 2점)

시각화 라이브러리와 matplotlib 의 그래프 종류에 대한 설명으로 옳지 **않은** 것은?

1. Matplotlib 은 기본적이고 유연한 시각화 도구이고, Seaborn 은 통계적 데이터 시각화에 적합하다.
2. `plt.bar()` 는 범주가 있는 데이터 값을 직사각형 막대로 표현한다.
3. `plt.hist()` 는 도수분포표를 그래프로 표현하며, 가로축은 계급이고 세로축은 도수이다.
4. `plt.pie()` 는 두 변수의 상관 관계를 평면에 점으로 표현한다.
5. `plt.boxplot()` 은 최솟값, 사분위수(Q1, Q2, Q3), 최댓값의 다섯 가지 요약 수치로 데이터를 표현한다.

## Q25 (객관식 · 2점)

matplotlib 으로 그래프를 꾸미고 저장하는 방법에 대한 설명으로 옳지 **않은** 것은?

1. `plt.plot(x, y, color="red", linestyle="--", marker="o")` 는 빨간색 파선(끊어진 선)을 긋고 점마다 원 모양 마커를 찍는다.
2. `plt.xlim(0, 5)` 는 x축의 표시 범위를 정하고, `plt.xticks(range(1, 5))` 는 x축 눈금을 1, 2, 3, 4 에 둔다.
3. `plt.legend(loc="upper left")` 는 `plt.plot()` 에 `label` 로 준 이름을 왼쪽 위에 범례로 표시한다.
4. `plt.savefig("my_plot.png")` 는 `plt.show()` 를 호출한 다음에 써야 그림이 저장된다.
5. `plt.hist(data, bins=4)` 의 `bins` 는 전체 범위를 몇 등분할지 정하고, `plt.pie()` 의 `autopct` 는 부채꼴 안에 표시할 숫자의 형식을 정한다.

## Q26 (객관식 · 2점)

다음 코드에서 산점도가 그려지는 칸은? `x`, `y`, `categories`, `values`, `data` 는 미리 만들어 둔 리스트입니다.

```python
import matplotlib.pyplot as plt

fig, axs = plt.subplots(2, 2)
axs[0, 0].plot(x, y)
axs[0, 1].bar(categories, values)
axs[1, 0].scatter(x, y)
axs[1, 1].hist(data)
plt.tight_layout()
plt.show()
```

1. 위 왼쪽
2. 위 오른쪽
3. 아래 왼쪽
4. 아래 오른쪽

## Q27 (단답 · 3점)

x 값이 `[1, 2, 3, 4, 5]`, y 값이 `[2, 4, 6, 8, 10]` 인 선 그래프에 제목, 축 이름, 그리드(격자)를 넣으려고 합니다. 그리드를 추가하는 줄의 빈칸(`____`)에 들어갈 함수 이름을 적으세요.

```python
import matplotlib.pyplot as plt

x = [1, 2, 3, 4, 5]
y = [2, 4, 6, 8, 10]
plt.plot(x, y)
plt.title("Line Graph")
plt.xlabel("X")
plt.ylabel("Y")
plt.____(True)
plt.show()
```

## Q28 (객관식 · 2점)

`df` 는 CSV 파일을 pandas 로 불러와 만든 DataFrame 이고, 2016년부터 2024년까지의 `연도` 열과 그 해의 `영치대수` 열이 있습니다. `import matplotlib.pyplot as plt` 를 한 상태에서, 가로축이 연도이고 세로축이 영치대수인 **선 그래프**를 그리는 코드는?

1. `plt.plot(df['연도'], df['영치대수'])`
2. `plt.plot(df['영치대수'], df['연도'])`
3. `plt.bar(df['연도'], df['영치대수'])`
4. `plt.scatter(df['연도'], df['영치대수'])`

## Q29 (객관식 · 2점)

다음 코드를 실행했을 때 출력되는 것은?

```python
import pandas as pd

data = {'ID': [1, 2, 3, 4, 5, 6], 'Price': [300, 150, 230, 400, 200, 250]}
df = pd.DataFrame(data)
print(df.tail())
```

**1번**

```
   ID  Price
0   1    300
1   2    150
2   3    230
3   4    400
4   5    200
```

**2번**

```
   ID  Price
1   2    150
2   3    230
3   4    400
4   5    200
5   6    250
```

**3번**

```
   ID  Price
0   2    150
1   3    230
2   4    400
3   5    200
4   6    250
```

**4번**

```
   ID  Price
5   6    250
```

## Q30 (객관식 · 2점)

다음 코드를 실행했을 때 출력되는 것은?

```python
import numpy as np

print(np.eye(2, 3))
```

**1번**

```
[[1. 1. 1.]
 [1. 1. 1.]]
```

**2번**

```
[[1. 0.]
 [0. 1.]
 [0. 0.]]
```

**3번**

```
[[1. 0. 0.]
 [0. 1. 0.]]
```

**4번**

```
[[1 0 0]
 [0 1 0]]
```

## Q31 (객관식 · 2점)

다음 코드를 실행했을 때 출력되는 것은?

```python
import numpy as np

a = np.array([[1, 2], [3, 4]])
b = np.array([[2, 0], [1, 3]])
print(np.dot(a, b))
```

**1번**

```
[[ 2  0]
 [ 3 12]]
```

**2번**

```
[[ 4  6]
 [10 12]]
```

**3번**

```
[[ 2  4]
 [10 14]]
```

**4번**

```
[[3 2]
 [4 7]]
```

## Q32 (객관식 · 2점)

다음 코드로 그린 히스토그램에 대한 설명으로 옳은 것은?

```python
import matplotlib.pyplot as plt

data = [1, 2, 2, 3, 3, 3, 4, 4, 4, 4]
plt.hist(data, bins=4, color="skyblue", edgecolor="black")
plt.title("Histogram")
plt.show()
```

1. 막대가 10개 그려지고, 막대의 높이는 왼쪽부터 `data` 에 적힌 값과 같다.
2. 막대가 4개 그려지고, 막대의 높이는 왼쪽부터 1, 2, 3, 4 이다.
3. 막대가 4개 그려지고, 막대의 높이는 모두 같다.
4. 막대는 그려지지 않고 점 10개가 찍힌다.

## Q33 (단답 · 3점)

pip 는 터미널(명령 프롬프트)에서 실행하는 Python 패키지 관리자입니다. 설치해 둔 pandas 패키지를 **제거**하려고 합니다. 빈칸(`____`)에 들어갈 단어를 적으세요.

```
pip ____ pandas
```

## Q34 (단답 · 3점)

matplotlib 으로 선 그래프를 그리려고 합니다. 빈칸(`____`)에 들어갈 모듈 이름을 적으세요.

```python
import matplotlib.____ as plt

plt.plot([1, 2, 3, 4], [10, 20, 25, 30])
plt.title("Line Plot")
plt.show()
```

## Q35 (객관식 · 2점)

다음 코드가 출력하는 표에 대한 설명으로 옳은 것은?

```python
import pandas as pd

data = {'ID': [1, 2, 3], 'Name': ['Alice', 'Bob', 'Charlie'], 'Age': [30, 35, 25]}
df = pd.DataFrame(data)
print(df.describe())
```

1. `ID`, `Name`, `Age` 세 열의 값이 위에서부터 5개 행까지 나온다.
2. 숫자 열인 `ID` 와 `Age` 만 나오고, 행에는 count, mean, std, min, 25%, 50%, 75%, max 가 나온다.
3. 열 이름과 열마다 비어 있지 않은 값의 수, 자료형이 나온다.
4. `ID`, `Name`, `Age` 세 열이 모두 나오고, `Name` 열의 mean 자리에는 NaN 이 나온다.

## Q36 (단답 · 3점)

`df` 를 `Age` 열의 값이 작은 순서로 정렬하려고 합니다. 빈칸(`____`)에 들어갈 메서드 이름을 적으세요.

```python
import pandas as pd

data = {'ID': [1, 2, 3], 'Name': ['Alice', 'Bob', 'Charlie'], 'Age': [30, 35, 25]}
df = pd.DataFrame(data)
sorted_df = df.____(by='Age')
print(sorted_df)
```

출력 결과는 아래와 같습니다.

```
   ID     Name  Age
2   3  Charlie   25
0   1    Alice   30
1   2      Bob   35
```

## Q37 (객관식 · 2점)

다음 코드를 실행했을 때 출력되는 것은?

```python
import pandas as pd

data = {'ID': [1, 2, 3], 'Name': ['Alice', 'Bob', 'Charlie'], 'Age': [30, 35, 25]}
df = pd.DataFrame(data)
df.drop(1)
df.sort_values(by='Age')
print(df)
```

**1번**

```
   ID     Name  Age
0   1    Alice   30
1   2      Bob   35
2   3  Charlie   25
```

**2번**

```
   ID     Name  Age
0   1    Alice   30
2   3  Charlie   25
```

**3번**

```
   ID     Name  Age
2   3  Charlie   25
0   1    Alice   30
1   2      Bob   35
```

**4번**

```
   ID     Name  Age
2   3  Charlie   25
0   1    Alice   30
```

## Q38 (객관식 · 2점)

다음 코드를 실행했을 때 출력되는 것은?

```python
import numpy as np

arr = np.array([[1, 2, 3], [4, 5, 6]])
print(arr.shape, arr.sum(), arr.mean())
```

1. `(2, 3) 21 3.5`
2. `(3, 2) 21 3.5`
3. `(2, 3) 21 3`
4. `(6,) 21 3.5`

## Q39 (객관식 · 2점)

CSV 파일과 엑셀 파일의 구조에 대한 설명으로 옳지 **않은** 것은?

1. CSV 파일은 줄바꿈으로 구분되는 행(레코드)으로 이루어지고, 각 행은 쉼표로 구분되는 열(필드)로 이루어진다.
2. CSV 파일은 텍스트 에디터에 내용을 적고 확장자를 `.csv` 로 저장해 만들 수 있다.
3. 엑셀 파일은 북(book)이라고 부르며, 북 하나에는 시트(sheet)를 하나만 둘 수 있다.
4. 엑셀의 시트는 행(row)과 열(column)을 가진 2차원 셀(cell)로 이루어진다.
