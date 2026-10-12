# 18차시 · 딥러닝 파이썬 패키지(1)

데이터를 표로 다루는 pandas, 배열과 행렬을 계산하는 numpy, 그래프를 그리는 matplotlib 을 배우는 차시입니다.
세 패키지는 파이썬 표준 모듈이 아니어서 `pip` 로 설치해야 쓸 수 있습니다. 스터디 프로그램은 패키지가 없는 컴퓨터에서도 풀 수 있게 이 차시를 객관식과 단답으로만 냅니다.
함수 이름, 인자의 모양, 출력 모양을 묻는 문제가 나오기 좋은 단원이라 아래 코드의 결과를 가리고 손으로 적어 보면 복습이 됩니다.

| 강의 절 | 내용 |
|---|---|
| 18.1 pandas 개요 | pip, Series, DataFrame, CSV·엑셀 읽기, `head`/`tail`/`info`/`describe`, `sample` |
| 18.2 pandas 활용 | 열 선택, 조건 필터링, 정렬, 열·행 추가, 행 삭제, `concat`, `merge`, 결측치, 중복 |
| 18.3 numpy 개요 | 배열 생성, `shape`/`dtype`, `zeros`/`ones`/`full`/`eye`/`identity`, 난수 배열 |
| 18.4 numpy 활용 | 요소별 연산, 통계 함수, 브로드캐스팅, 행렬 곱, 인덱싱·슬라이싱, 조건 필터링 |
| 18.5 matplotlib 개요 | 선 그래프, 막대 그래프, 히스토그램, 산점도, 파이 차트, 박스 플롯 |
| 18.6 matplotlib 활용 | 색·선 스타일·마커, 축 범위와 눈금, 범례, 저장, subplot |

## 1. 패키지 설치와 불러오기

pip 는 Python 패키지 관리자(Package Installer for Python)입니다. 라이브러리를 설치하고 관리할 때 쓰고, 파이썬 코드가 아니라 터미널(명령 프롬프트)에서 실행합니다.

| 하는 일 | 명령 |
|---|---|
| 패키지 설치 | `pip install <패키지명>` |
| 패키지 제거 | `pip uninstall <패키지명>` |
| 설치된 패키지 목록 확인 | `pip list` |

| 패키지 | 설치 | 불러오기 |
|---|---|---|
| pandas | `pip install pandas` | `import pandas as pd` |
| numpy | `pip install numpy` (pandas 를 설치하면 함께 설치됨) | `import numpy as np` |
| matplotlib | `pip install matplotlib` | `import matplotlib.pyplot as plt` |
| openpyxl | `pip install openpyxl` | pandas 가 엑셀 파일을 읽을 때 필요 |

## 2. pandas: Series 와 DataFrame

- pandas 는 데이터 분석과 조작을 위한 라이브러리입니다. CSV 파일 같은 데이터를 읽어 원하는 형식으로 바꿉니다.
- CSV(Comma Separated Values)는 데이터를 쉼표로 구분한 파일입니다.
- **Series** 는 라벨이 있는 1차원 배열이고, **DataFrame** 은 행과 열에 라벨이 있는 2차원 테이블입니다. 테이블의 가로줄이 행(row), 세로줄이 열(column)입니다.

Series 는 리스트나 딕셔너리로 만듭니다. 리스트로 만들면 인덱스가 0부터 붙고, 딕셔너리로 만들면 key 가 인덱스로 들어갑니다.

```python
import pandas as pd

s1 = pd.Series([10, 20, 30])                    # 인덱스 0, 1, 2
s2 = pd.Series({'a': 10, 'b': 20, 'c': 30})     # 인덱스 a, b, c
print(s2)
```

```
a    10
b    20
c    30
dtype: int64
```

DataFrame 은 중첩 리스트나 딕셔너리로 만듭니다. 중첩 리스트는 안쪽 리스트 하나가 한 행이고 열 이름을 `columns` 로 줍니다. 딕셔너리는 key 가 열 이름이고 value 리스트가 그 열의 값입니다.

```python
data = [
    [1, 'Alice', 30],
    [2, 'Bob', 35],
    [3, 'Charlie', 25]
]
df = pd.DataFrame(data, columns=['ID', 'Name', 'Age'])      # 행 단위로 적음

data = {
    'ID': [1, 2, 3],
    'Name': ['Alice', 'Bob', 'Charlie'],
    'Age': [30, 35, 25]
}
df = pd.DataFrame(data)                                      # 열 단위로 적음
print(df)
```

```
   ID     Name  Age
0   1    Alice   30
1   2      Bob   35
2   3  Charlie   25
```

두 코드는 같은 DataFrame 을 만듭니다. 출력의 맨 윗줄이 열 이름이고 맨 왼쪽의 0, 1, 2 가 인덱스(행 라벨)입니다.

## 3. pandas: 데이터 불러오기와 살펴보기

CSV 파일은 줄바꿈으로 구분되는 행(레코드)으로 이루어지고, 각 행은 쉼표로 구분되는 열(필드)로 이루어집니다. 필드를 큰따옴표로 둘러싸도 되지만 파일 안에서 통일해야 합니다. 텍스트 에디터에 아래처럼 적고 확장자를 `.csv` 로 저장하면 CSV 파일이 됩니다.

```
ID,이름,가격
1,비누,300
2,장갑,150
3,마스크,230
4,손수건,400
5,볼펜,200
6,건전지,250
```

```python
df_csv = pd.read_csv('data.csv')        # CSV 파일을 DataFrame 으로 읽음
df_xl = pd.read_excel('data.xlsx')      # 엑셀 파일을 읽음, openpyxl 이 있어야 함
```

엑셀 파일은 북(book)이라고 부르고, 북 하나에 시트(sheet)가 여러 개 들어갑니다. 시트는 행과 열로 된 2차원 셀(cell)로 이루어집니다.

| 코드 | 하는 일 |
|---|---|
| `df.head()` | 위에서부터 5개 행 |
| `df.tail()` | 아래에서부터 5개 행 |
| `df.info()` | 요약 정보(행 수, 열 이름, 열마다 비어 있지 않은 값의 수와 자료형) |
| `df.describe()` | 숫자 열의 기술 통계: count, mean, std, min, 25%, 50%, 75%, max |
| `df.sample(2)` | 무작위로 2개 행 |
| `df.sample(frac=0.5)` | 무작위로 전체의 50% 에 해당하는 행 |

- 위 CSV 는 6행이라 `df_csv.head()` 는 인덱스 0~4(비누~볼펜), `df_csv.tail()` 은 인덱스 1~5(장갑~건전지)를 보여 줍니다.
- `describe()` 는 숫자 열만 계산합니다. `ID`, `Name`, `Age` 열이 있는 DataFrame 이면 결과에 `ID` 와 `Age` 만 나옵니다.
- `sample()` 은 무작위로 뽑기 때문에 실행할 때마다 결과가 달라질 수 있고, 뽑힌 행의 인덱스 순서도 섞여 나옵니다.
- 슬라이드의 `print(df.info())` 출력 결과에는 `<bound method DataFrame.info of ...>` 가 적혀 있습니다. 이 모양은 괄호를 빼고 `print(df.info)` 를 실행했을 때 나옵니다. 괄호를 붙여 호출하면 열 이름과 자료형이 정리된 요약이 나옵니다.

## 4. pandas: 데이터 조작

2절의 `df`(ID, Name, Age 3행)에서 이어집니다.

```python
print(df['Name'])               # 열 하나를 고름, 결과는 Series
filtered = df[df['Age'] > 30]   # 조건이 True 인 행만 남김
print(filtered)
```

```
   ID Name  Age
1   2  Bob   35
```

`df['Age'] > 30` 은 행마다 True/False 가 담긴 Series 입니다. 이것을 `df[...]` 안에 넣으면 True 인 행만 남고, 남은 행의 인덱스는 원래 값(1)을 유지합니다.

```python
sorted_df = df.sort_values(by='Age')    # Age 가 작은 순서로 정렬한 새 DataFrame
print(sorted_df)
```

```
   ID     Name  Age
2   3  Charlie   25
0   1    Alice   30
1   2      Bob   35
```

정렬해도 인덱스는 행을 따라다니므로 2, 0, 1 순서로 나옵니다.

```python
df['Salary'] = [50000, 60000, 70000]            # 열 추가
df.loc[len(df)] = [4, 'David', 40, 80000]       # 행 추가, len(df) 가 3 이라 인덱스 3 에 들어감
df = df.drop(1)                                 # 인덱스가 1 인 행 삭제
print(df)
```

```
   ID     Name  Age  Salary
0   1    Alice   30   50000
2   3  Charlie   25   70000
3   4    David   40   80000
```

- `drop()` 과 `sort_values()` 는 원본을 바꾸지 않고 새 DataFrame 을 돌려줍니다. `df = df.drop(1)` 처럼 다시 담아야 `df` 에 반영됩니다.
- 행을 지워도 인덱스는 다시 매겨지지 않아 0, 2, 3 이 남습니다.

`pd.concat()` 은 DataFrame 을 위아래로 이어 붙입니다(행 연결). 이어 붙일 DataFrame 들을 리스트로 묶어 넘깁니다.

```python
data2 = {
    'ID': [5, 6],
    'Name': ['Eve', 'Frank'],
    'Age': [28, 33]
}
df2 = pd.DataFrame(data2)
concated = pd.concat([df, df2])
print(concated)
```

```
   ID     Name  Age   Salary
0   1    Alice   30  50000.0
2   3  Charlie   25  70000.0
3   4    David   40  80000.0
0   5      Eve   28      NaN
1   6    Frank   33      NaN
```

- `df2` 에 없는 `Salary` 열은 NaN 으로 채워집니다. NaN(Not a Number)은 결측값(NA, Not Available)을 나타내며, 정의되지 않은 값, 표현할 수 없는 값, 누락된 값에 씁니다. 값이 없는 자리는 `None` 으로 입력해도 됩니다.
- NaN 이 들어간 `Salary` 열은 실수로 바뀌어 `50000.0` 처럼 출력됩니다.
- 인덱스는 각 DataFrame 의 것을 가져와 0, 2, 3, 0, 1 이 됩니다.

`pd.merge()` 는 두 DataFrame 에 공통으로 있는 열의 값이 같은 행끼리 옆으로 붙입니다(열 병합).

```python
data3 = {
    'ID': [1, 2, 3, 4, 5, 6],
    'Department': ['HR', 'Engineering', 'Sales', 'R&D', 'Finance', 'Planning']
}
df3 = pd.DataFrame(data3)
merged = pd.merge(concated, df3)
print(merged)
```

```
   ID     Name  Age   Salary Department
0   1    Alice   30  50000.0         HR
1   3  Charlie   25  70000.0      Sales
2   4    David   40  80000.0        R&D
3   5      Eve   28      NaN    Finance
4   6    Frank   33      NaN   Planning
```

`ID` 가 2 인 행은 `concated` 에 없어서 결과에서 빠집니다. `merge()` 결과의 인덱스는 0부터 새로 매겨집니다.

## 5. pandas: 결측치와 중복 처리

```python
print(merged.isnull().sum())    # 열마다 결측치 개수
```

```
ID            0
Name          0
Age           0
Salary        2
Department    0
dtype: int64
```

```python
meanVal = merged['Salary'].mean()                       # NaN 을 빼고 구한 평균
merged['Salary'] = merged['Salary'].fillna(meanVal)     # NaN 자리만 평균으로 채움
```

`mean()` 은 NaN 을 빼고 계산합니다. 위 예에서는 (50000 + 70000 + 80000) / 3 = 66666.666667 이 Eve 와 Frank 의 `Salary` 에 들어갑니다.

```python
data1 = {
    'ID': [1, 3],
    'Name': ['Alice', 'Charlie'],
    'Age': [30, 25],
    'Salary': [50000, 70000],
    'Department': ['HR', 'Sales']
}
df1 = pd.DataFrame(data1)
df1 = pd.concat([merged, df1])
print(df1.duplicated())                 # 앞에 같은 행이 있으면 True
df1_1 = df1.drop_duplicates()           # 중복된 행을 뺀 새 DataFrame
```

```
0    False
1    False
2    False
3    False
4    False
0     True
1     True
dtype: bool
```

`duplicated()` 는 중복 여부만 알려 주고, `drop_duplicates()` 가 중복된 행을 지운 결과를 돌려줍니다.

## 6. numpy: 배열 만들기

NumPy(Numerical Python)는 다차원 배열과 행렬 연산을 지원하는 라이브러리이고, 과학 계산에 쓰는 함수를 제공합니다.

```python
import numpy as np

arr = np.array([1, 2, 3, 4, 5])
print(arr)          # [1 2 3 4 5]   쉼표 없이 출력됨
print(arr.shape)    # (5,)          배열의 모양
print(arr.dtype)    # int64         데이터 타입
```

| 코드 | 만들어지는 배열 |
|---|---|
| `np.zeros((3, 3))` | 0 으로 채운 3행 3열 |
| `np.ones((2, 4))` | 1 로 채운 2행 4열 |
| `np.full((2, 2), 7)` | 7 로 채운 2행 2열 |
| `np.eye(2, 3)` | 2행 3열, 대각선 자리만 1 이고 나머지는 0 |
| `np.identity(3)` | 3행 3열 단위 행렬 |
| `np.random.rand(3, 3)` | 0 이상 1 미만의 실수 난수 3행 3열 |
| `np.random.randint(1, 10, (3, 3))` | 1 이상 10 미만의 정수 난수 3행 3열 |

```python
print(np.zeros((3, 3)))
print(np.full((2, 2), 7))
print(np.eye(2, 3))
```

```
[[0. 0. 0.]
 [0. 0. 0.]
 [0. 0. 0.]]
[[7 7]
 [7 7]]
[[1. 0. 0.]
 [0. 1. 0.]]
```

- `zeros`, `ones`, `eye`, `identity` 로 만든 배열은 요소가 실수라서 `0.`, `1.` 처럼 점이 붙어 출력됩니다. `np.full((2, 2), 7)` 은 넘긴 값이 정수라 `7` 로 출력됩니다.
- 단위 행렬은 대각선 위의 요소가 1 이고 나머지는 모두 0 인 행렬입니다.
- 2차원 배열의 `shape` 는 `(행 수, 열 수)` 입니다. `np.array([[1, 2, 3], [4, 5, 6]]).shape` 는 `(2, 3)` 입니다.
- `zeros`, `ones`, `full` 은 모양을 `(3, 3)` 처럼 튜플 하나로 받습니다. `rand(3, 3)` 과 `eye(2, 3)` 은 숫자를 따로 받습니다.

## 7. numpy: 연산과 인덱싱

배열과 숫자의 연산은 요소마다 적용됩니다. 합계, 평균, 최댓값, 최솟값은 배열의 메서드로 구합니다.

```python
arr = np.array([1, 2, 3, 4])
print(arr + 5)      # [6 7 8 9]
print(arr * 2)      # [2 4 6 8]
print(arr.sum())    # 10
print(arr.mean())   # 2.5
print(arr.max())    # 4
print(arr.min())    # 1
```

브로드캐스팅은 모양이 다른 배열끼리 연산할 때 모양을 맞춰 계산하는 기능입니다. 모양이 `(3,)` 인 배열과 `(3, 1)` 인 배열을 더하면 3행 3열이 됩니다.

```python
arr1 = np.array([1, 2, 3])
arr2 = np.array([[1], [2], [3]])
print(arr1 + arr2)
```

```
[[2 3 4]
 [3 4 5]
 [4 5 6]]
```

각 행은 `arr2` 의 값 하나에 `arr1` 전체를 더한 결과입니다. 첫 행은 1 + [1, 2, 3], 둘째 행은 2 + [1, 2, 3] 입니다.

행렬 곱은 `np.dot()` 으로 구합니다. `*` 는 같은 자리의 요소끼리 곱하는 연산이라 결과가 다르게 나옵니다.

```python
matrix1 = np.array([[1, 2], [3, 4]])
matrix2 = np.array([[5, 6], [7, 8]])
print(np.dot(matrix1, matrix2))
print(matrix1 * matrix2)
```

```
[[19 22]
 [43 50]]
[[ 5 12]
 [21 32]]
```

행렬 곱의 각 자리는 앞 행렬의 행과 뒤 행렬의 열을 곱해 더한 값입니다. 19 = 1×5 + 2×7, 22 = 1×6 + 2×8, 43 = 3×5 + 4×7, 50 = 3×6 + 4×8 입니다.

```python
arr = np.array([10, 20, 30, 40])
print(arr[2])           # 30

arr = np.array([[1, 2, 3], [4, 5, 6]])
print(arr[1, 2])        # 6         두 번째 행, 세 번째 열
print(arr[0, :])        # [1 2 3]   첫 번째 행
print(arr[:, 1])        # [2 5]     두 번째 열

arr = np.array([1, 2, 3, 4, 5])
filtered = arr[arr > 3]
print(filtered)         # [4 5]     조건이 참인 요소만 남음

df = pd.DataFrame(arr, columns=['Value'])       # 배열을 DataFrame 으로 변환
```

2차원 배열은 `arr[행, 열]` 순서로 쓰고 둘 다 0부터 셉니다. `:` 는 그 방향 전체를 고릅니다.

## 8. matplotlib: 기본 사용법과 그래프 종류

- 데이터 시각화는 데이터를 그래프로 표현해 이해를 돕는 과정입니다.
- matplotlib 은 정적, 애니메이션, 대화형 시각화를 만드는 라이브러리입니다. 플롯(plot)은 두 개 이상의 변수 간의 관계를 보여 주는 그래프입니다.
- Matplotlib 은 기본적이고 유연한 시각화 도구이고, Seaborn 은 통계적 데이터 시각화에 적합합니다.

```python
import matplotlib.pyplot as plt

x = [1, 2, 3, 4]
y = [10, 20, 25, 30]
plt.plot(x, y)              # 선 그래프, 첫 인자가 가로축
plt.title("Line Plot")      # 제목
plt.xlabel("X-axis")        # x축 이름
plt.ylabel("Y-axis")        # y축 이름
plt.show()                  # 그래프를 화면에 표시
```

| 그래프 | 코드 | 설명 |
|---|---|---|
| 선 그래프 | `plt.plot(x, y)` | 점을 선으로 이음 |
| 막대 그래프(Bar Chart) | `plt.bar(categories, values)` | 범주가 있는 데이터 값을 직사각형 막대로 표현 |
| 히스토그램(Histogram) | `plt.hist(data, bins=4, color="skyblue", edgecolor="black")` | 도수분포표를 그래프로 표현. 가로축은 계급, 세로축은 도수(횟수나 개수) |
| 산점도(Scatter Plot) | `plt.scatter(x, y, color="green")` | 두 변수의 상관 관계를 직교 좌표계의 평면에 점으로 표현 |
| 파이 차트(Pie Chart, 원 그래프) | `plt.pie(sizes, labels=labels, autopct="%1.1f%%", startangle=90)` | 범주별 구성 비율을 원형으로 표현 |
| 박스 플롯(Box Plot) | `plt.boxplot(data)` | 수치 데이터를 다섯 가지 요약 수치로 표현 |

- `bins` 는 전체 범위를 몇 등분할지 정합니다. `data = [1, 2, 2, 3, 3, 3, 4, 4, 4, 4]` 를 `bins=4` 로 그리면 막대 높이가 1, 2, 3, 4 입니다.
- `autopct` 는 부채꼴 안에 표시할 숫자의 형식이고(`"%1.1f%%"` 는 `15.0%` 모양), `startangle` 은 시작 각도입니다.
- 박스 플롯의 다섯 가지 요약 수치는 최솟값, 제1사분위수(Q1), 제2사분위수 또는 중위수(Q2), 제3사분위수(Q3), 최댓값입니다.

## 9. matplotlib: 꾸미기, 저장, subplot

```python
plt.plot(x, y, color="red", linestyle="--", marker="o")     # 빨간색 파선(끊어진 선), 원 모양 마커

plt.xlim(0, 5)                      # x축 표시 범위
plt.ylim(0, 40)                     # y축 표시 범위
plt.xticks(range(1, 5))             # x축 눈금 1, 2, 3, 4
plt.yticks(range(0, 41, 10))        # y축 눈금 0, 10, 20, 30, 40

plt.plot(x, y, label="Data 1")
plt.plot(x1, y2, label="Data 2")
plt.legend(loc="upper left")        # label 로 준 이름을 왼쪽 위에 범례로 표시

plt.savefig("my_plot.png")          # 그림 파일로 저장
plt.show()
```

`plt.show()` 를 호출하면 그림이 해제되므로 `plt.savefig()` 는 `plt.show()` 보다 먼저 호출해야 합니다.

```python
fig, axs = plt.subplots(2, 2)       # 2행 2열로 나눈 칸
axs[0, 0].plot(x, y)                # 위 왼쪽
axs[0, 1].bar(categories, values)   # 위 오른쪽
axs[1, 0].scatter(x, y)             # 아래 왼쪽
axs[1, 1].hist(data)                # 아래 오른쪽
plt.tight_layout()                  # 칸끼리 겹치지 않게 간격을 맞춤
plt.show()
```

`axs` 도 `axs[행, 열]` 순서로 칸을 고릅니다.

## 10. 과제에 나온 코드

과제를 풀려면 슬라이드에 없는 표현도 써야 합니다. 두 조건을 잇는 `&`, 연속한 정수 배열을 만드는 `np.arange()`, 행마다 계산하게 하는 `axis=1`, 격자를 그리는 `plt.grid()` 가 과제에서 새로 나옵니다.

CSV 파일을 불러와 열마다 평균, 최댓값, 최솟값을 출력합니다.

```python
df = pd.read_csv('data.csv')            # Name, Age, Salary 열이 있는 파일
for col in ['Age', 'Salary']:
    print(f"{col} 평균: {df[col].mean()}, 최댓값: {df[col].max()}, 최솟값: {df[col].min()}")
```

```
Age 평균: 29.5, 최댓값: 35, 최솟값: 25
Salary 평균: 58750.0, 최댓값: 70000, 최솟값: 50000
```

30세 이상이면서 연봉이 60000 이상인 행만 고릅니다. 조건마다 괄호로 묶고 `&` 로 잇습니다. `and` 를 쓰면 오류가 나고, "또는"은 `|` 로 씁니다.

```python
filtered = df[(df['Age'] >= 30) & (df['Salary'] >= 60000)]
```

1부터 10까지의 배열을 만들어 제곱하고 통계를 냅니다. `np.arange(1, 11)` 은 `range(1, 11)` 처럼 끝값을 빼고 만듭니다.

```python
arr = np.arange(1, 11)
squared = arr ** 2
print("원본 배열:", arr)
print("제곱 배열:", squared)
print(f"평균: {squared.mean()}, 최댓값: {squared.max()}, 최솟값: {squared.min()}")
```

```
원본 배열: [ 1  2  3  4  5  6  7  8  9 10]
제곱 배열: [  1   4   9  16  25  36  49  64  81 100]
평균: 38.5, 최댓값: 100, 최솟값: 1
```

3행 4열 난수 행렬에서 행마다 최댓값을 구합니다. `axis=1` 은 행마다(가로 방향으로), `axis=0` 은 열마다(세로 방향으로) 계산합니다.

```python
arr = np.random.randint(1, 13, (3, 4))
print("원본 행렬:")
print(arr)
print("각 행의 최댓값:", arr.max(axis=1))
```

```
원본 행렬:
[[ 3 10  5  7]
 [ 6  8  2  1]
 [12  4 11  9]]
각 행의 최댓값: [10  8 12]
```

난수라서 실행할 때마다 행렬이 달라집니다. 위 행렬에서 `arr.max()` 는 12, `arr.max(axis=0)` 은 `[12 10 11  9]` 입니다.

제목, 축 이름, 그리드를 넣은 선 그래프를 그립니다.

```python
x = [1, 2, 3, 4, 5]
y = [2, 4, 6, 8, 10]
plt.plot(x, y)
plt.title("Line Graph")
plt.xlabel("X")
plt.ylabel("Y")
plt.grid(True)              # 격자 표시
plt.show()
```

주간 과제는 공공데이터 CSV 파일을 `pd.read_csv()` 로 읽어 DataFrame 으로 만든 다음, 연도 열을 가로축에, 영치대수 열을 세로축에 넣어 `plt.plot(df['연도'], df['영치대수'])` 로 선 그래프를 그리는 문제입니다. 열 이름은 내려받은 파일에 적힌 대로 씁니다.

## 시험에서 헷갈리기 쉬운 점

- 함수 이름의 대소문자를 구분합니다. `pd.DataFrame()`, `pd.Series()` 는 대문자로 시작하고 `np.array()`, `np.zeros()`, `pd.read_csv()` 는 소문자로 쓰며, 과제의 오답 보기에 나온 `np.Array()` 나 `pd.Table()` 같은 이름은 numpy 와 pandas 에 들어 있지 않습니다.
- 불러올 때 붙이는 이름은 `pd`, `np`, `plt` 입니다. matplotlib 은 `import matplotlib.pyplot as plt` 로 `pyplot` 까지 적습니다.
- `pip install` 은 설치, `pip uninstall` 은 제거, `pip list` 는 목록 확인입니다. numpy 는 pandas 를 설치할 때 함께 설치되고, 엑셀 파일을 읽으려면 openpyxl 을 따로 설치합니다.
- Series 를 리스트로 만들면 인덱스가 0, 1, 2 이고 딕셔너리로 만들면 key 가 인덱스입니다. DataFrame 을 딕셔너리로 만들면 key 가 열 이름입니다.
- DataFrame 을 중첩 리스트로 만들 때는 안쪽 리스트가 한 행입니다. 열 단위로 묶은 리스트를 넣으면 행과 열이 뒤바뀝니다.
- `head()` 와 `tail()` 은 5개 행을 보여 줍니다. `info()` 는 요약 정보, `describe()` 는 기술 통계입니다.
- `sample()` 은 무작위라 결과가 정해져 있지 않습니다. `sample(2)` 는 2개, `sample(frac=0.5)` 는 절반입니다.
- 조건 필터링, `drop()`, `sort_values()` 뒤에는 인덱스가 원래 값으로 남습니다. `concat()` 도 각자의 인덱스를 가져오고, `merge()` 결과만 0부터 새로 매겨집니다.
- `df.drop(1)` 의 1 은 순서가 아니라 인덱스 값입니다. `drop()` 은 새 DataFrame 을 돌려주므로 `df = df.drop(1)` 로 다시 담습니다.
- 행 추가는 `df.loc[len(df)] = [...]` 입니다. 넣는 리스트의 길이는 열의 개수와 같아야 합니다.
- `pd.concat([df, df2])` 는 대괄호로 묶어 넘깁니다. `concat` 은 위아래로 잇고, `merge` 는 공통 열의 값이 같은 행끼리 옆으로 붙입니다. `merge` 에서 한쪽에만 있는 값의 행은 빠집니다.
- NaN 은 Not a Number 의 줄임말이고 결측값을 나타냅니다. 결측치 개수는 `isnull().sum()`, 채우기는 `fillna(값)` 입니다. `mean()` 은 NaN 을 빼고 평균을 냅니다.
- `duplicated()` 는 True/False 를 돌려주고 `drop_duplicates()` 는 중복을 지운 DataFrame 을 돌려줍니다.
- 열을 출력할 때 맨 아래에 나오는 문자열 열의 자료형 표기는 강의 자료에 `dtype: object` 로 적혀 있습니다. 최신 pandas 에서는 `str` 로 나옵니다.
- NumPy 배열은 `[1 2 3]` 처럼 쉼표 없이 출력됩니다. 리스트의 `[1, 2, 3]` 과 구분합니다.
- 1차원 배열의 `shape` 는 `(5,)` 입니다. 요소가 하나인 튜플이라 쉼표가 붙습니다.
- `np.zeros((3, 3))` 은 괄호가 두 겹입니다. 모양을 튜플로 넘기기 때문입니다. 출력은 `0.` 처럼 실수로 나옵니다.
- `np.ones()` 는 전부 1 이고, `np.eye()` 와 `np.identity()` 는 대각선만 1 입니다.
- `np.random.rand()` 는 0 이상 1 미만의 실수, `np.random.randint(1, 10, ...)` 는 1 이상 10 미만의 정수입니다. 끝값 10 은 나오지 않습니다.
- 리스트의 `[1, 2, 3] * 2` 는 `[1, 2, 3, 1, 2, 3]` 이고, 배열의 `np.array([1, 2, 3]) * 2` 는 `[2 4 6]` 입니다.
- 두 행렬의 `*` 는 같은 자리끼리 곱하고, 행렬 곱은 `np.dot()` 입니다.
- `arr[1, 2]` 는 두 번째 행의 세 번째 열입니다. `arr[0, :]` 는 첫 번째 행, `arr[:, 1]` 은 두 번째 열입니다.
- `arr[arr > 3]` 과 `df[df['Age'] > 30]` 은 같은 꼴입니다. 대괄호 안의 조건이 True 인 것만 남깁니다. `>` 와 `>=` 를 구분해 경계값이 들어가는지 확인합니다.
- `plt.title()` 로 제목을 붙이고 `plt.xlabel()`, `plt.ylabel()` 로 가로축과 세로축의 이름을 붙이므로, 코드에 `plt.title()` 줄이 없으면 제목 없는 그래프가 그려집니다.
- `plt.xlim()` 은 축의 표시 범위이고 `plt.xticks()` 는 눈금 위치입니다. `range(1, 5)` 는 1, 2, 3, 4 입니다.
- 범례는 `plt.plot(..., label="이름")` 으로 이름을 주고 `plt.legend()` 를 불러야 나옵니다.
- `plt.savefig()` 는 `plt.show()` 보다 앞에 씁니다.
- 막대 그래프는 범주별 값을, 히스토그램은 구간별 개수를 막대로 그립니다. 산점도는 점만 찍고 선 그래프는 점을 선으로 잇습니다.
- `plt.subplots(2, 2)` 의 `axs[1, 0]` 은 아래 왼쪽 칸입니다. 함수 이름은 끝에 s 가 붙은 `subplots` 입니다.
