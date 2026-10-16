# 20차시 퀴즈: Seaborn·OpenCV

> 코드를 실행하지 말고 눈으로 풀어 보세요. 답은 `submissions/<내 ID>/s20/quiz.py` 에 적습니다.

## Q1 (객관식 · 2점)

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

## Q2 (객관식 · 2점)

Seaborn 과 OpenCV 에 대한 설명으로 옳지 **않은** 것은?

1. Seaborn 은 통계 그래프를 짧은 코드로 그리는 파이썬 데이터 시각화 라이브러리이다.
2. Seaborn 은 Matplotlib 위에서 동작하므로 `plt.title()`, `plt.show()` 와 함께 쓴다.
3. OpenCV 는 실시간 컴퓨터 비전을 위한 라이브러리로, 이미지와 영상을 처리하는 기능을 제공한다.
4. OpenCV 는 `pip install opencv-python` 으로 설치하고 `import opencv` 로 불러온다.

## Q3 (객관식 · 2점)

Seaborn 에서 두 변수 간의 관계를 시각적으로 표현하기 위해 사용하는 함수는?

1. `sns.distplot()`
2. `sns.histplot()`
3. `sns.violinplot()`
4. `sns.scatterplot()`

## Q4 (객관식 · 2점)

OpenCV 에서 이미지의 크기를 조정하는 함수는?

1. `cv2.resize()`
2. `cv2.rescale()`
3. `cv2.scale()`
4. `cv2.transform()`

## Q5 (객관식 · 2점)

OpenCV 에서 이미지를 다른 색상 공간으로 변환하는 함수는?

1. `cv2.convertColor()`
2. `cv2.cvtColor()`
3. `cv2.changeColor()`
4. `cv2.colorTransform()`

## Q6 (객관식 · 2점)

`cv2.imread()` 로 읽은 컬러 이미지 `image` 를 그레이스케일(흑백)로 변환하려고 합니다. OpenCV 는 컬러 이미지의 색을 B, G, R 순서로 다룹니다. 빈칸에 들어갈 플래그는?

```python
gray = cv2.cvtColor(image, ____)
```

1. `cv2.COLOR_BGR2GRAY`
2. `cv2.COLOR_RGB2GRAY`
3. `cv2.GREY`
4. `cv2.COLOR_GRAY`

## Q7 (단답 · 3점)

Seaborn 에 들어 있는 붓꽃 샘플 데이터를 데이터프레임으로 불러오려고 합니다. 빈칸에 들어갈 함수 이름을 적으세요. 대소문자와 밑줄을 구분합니다.

```python
import seaborn as sns

iris = sns.____("iris")
```

## Q8 (객관식 · 2점)

Seaborn 함수와 그 설명의 연결이 옳지 **않은** 것은?

1. `sns.lmplot()`: 산점도에 선형 회귀선을 함께 그려 두 변수의 선형적 관계를 보여 준다.
2. `sns.histplot()`: 데이터의 분포를 막대로 보여 주며, `kde=True` 를 주면 분포 곡선을 함께 그린다.
3. `sns.boxplot()`: 변수 쌍마다 산점도를 격자 모양으로 그려 여러 변수 간의 관계를 한 번에 보여 준다.
4. `sns.violinplot()`: 상자 그림과 커널 밀도 추정을 결합한 형태이며, `inner="quart"` 를 주면 내부에 사분위수를 표시한다.

## Q9 (객관식 · 2점)

다음 코드로 그린 산점도에 대한 설명으로 옳은 것은?

```python
import seaborn as sns
import matplotlib.pyplot as plt

iris = sns.load_dataset("iris")
sns.scatterplot(data=iris,
                x="petal_length",
                y="petal_width",
                hue="species",
                style="species")
plt.title("Scatter Plot Example")
plt.show()
```

1. `hue="species"` 는 종마다 점의 색을, `style="species"` 는 종마다 점(마커)의 모양을 다르게 한다.
2. `hue="species"` 는 종마다 점(마커)의 모양을, `style="species"` 는 종마다 점의 색을 다르게 한다.
3. `hue` 와 `style` 에 같은 열을 주었으므로 오류가 발생한다.
4. `style="species"` 는 그래프의 배경 스타일을 `species` 라는 테마로 바꾼다.

## Q10 (객관식 · 2점)

평균이 50, 표준편차가 10 인 정규 분포 데이터 1000개를 만들어 히스토그램으로 그리려고 합니다. (가)와 (나)에 들어갈 코드로 옳은 것은?

```python
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt

data = (가)
(나)
plt.show()
```

1. (가) `np.random.normal(1000, 50, 10)` (나) `sns.histplot(data)`
2. (가) `np.random.rand(50, 10, 1000)` (나) `sns.histplot(data)`
3. (가) `np.random.normal(50, 10, 1000)` (나) `sns.histplot(data)`
4. (가) `np.random.normal(50, 10, 1000)` (나) `sns.hist(data)`

## Q11 (객관식 · 2점)

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

## Q12 (객관식 · 2점)

다음은 강의에서 붓꽃 종별 꽃받침 길이를 상자 그림으로 그린 코드입니다. 이 데이터에서 종별 꽃받침 길이의 중앙값은 setosa 5.0, versicolor 5.9, virginica 6.5 입니다. 그려진 그래프에 대한 설명으로 옳은 것은?

```python
iris = sns.load_dataset("iris")
sns.boxplot(data=iris, x="species", y="sepal_length")
plt.title("Box Plot Example")
plt.show()
```

1. x 축에는 꽃받침 길이가, y 축에는 붓꽃 종이 놓인다.
2. 상자가 가장 위쪽에 그려지는 종은 virginica 이고, 이것을 근거로 꽃받침 길이가 가장 긴 종은 virginica 라고 말할 수 있다.
3. 세 종의 데이터가 합쳐져 상자가 한 개만 그려진다.
4. 상자 그림은 분포를 곡선으로만 보여 주는 그래프라서 이상치는 확인할 수 없다.

## Q13 (객관식 · 2점)

`sns.set_theme()` 함수는 `style` 로 그래프의 배경 스타일을, `palette` 로 색상 팔레트를 정합니다. 다음 중 `style` 에 줄 수 **없는** 값은?

1. `"darkgrid"`
2. `"whitegrid"`
3. `"ticks"`
4. `"pastel"`

## Q14 (객관식 · 2점)

이미지 파일을 읽어 창에 보여 주고, 키를 누르면 창을 닫는 프로그램입니다. (가), (나), (다)에 들어갈 함수 이름을 순서대로 바르게 적은 것은?

```python
import cv2

image = cv2.(가)('sample.jpg')
cv2.(나)('Loaded Image', image)
cv2.(다)(0)
cv2.destroyAllWindows()
```

1. (가) `imread` (나) `imshow` (다) `waitKey`
2. (가) `imshow` (나) `imread` (다) `waitKey`
3. (가) `imread` (나) `imshow` (다) `waitkey`
4. (가) `read` (나) `show` (다) `waitKey`

## Q15 (단답 · 3점)

컬러 이미지를 흑백(그레이스케일)으로 변환해 화면에 보여 주는 프로그램입니다. 빈칸에 들어갈 함수 이름을 적으세요. 대소문자를 구분합니다.

```python
import cv2

image = cv2.imread('color.jpg')
gray = cv2.____(image, cv2.COLOR_BGR2GRAY)
cv2.imshow('Grayscale Image', gray)
cv2.waitKey(0)
cv2.destroyAllWindows()
```

## Q16 (단답 · 3점)

이미지에서 엣지(윤곽선)를 검출해 화면에 보여 주는 프로그램입니다. 빈칸에 들어갈 함수 이름을 적으세요. 대소문자를 구분합니다.

```python
import cv2

image = cv2.imread('sample.jpg')
edges = cv2.____(image, 100, 200)
cv2.imshow('Edge Detection', edges)
cv2.waitKey(0)
cv2.destroyAllWindows()
```

## Q17 (객관식 · 2점)

OpenCV 의 이미지 처리 함수에 대한 설명으로 옳지 **않은** 것은?

1. `cv2.Canny(image, 100, 200)` 에서 100 은 최소 임계값, 200 은 최대 임계값이다.
2. `cv2.GaussianBlur(image, (15, 15), 0)` 에서 `(15, 15)` 는 커널 크기이고, 커널이 클수록 이미지가 더 선명해진다.
3. `cv2.CascadeClassifier()` 는 사전 학습된 Haar Cascade 모델의 XML 파일을 받아 얼굴 같은 객체를 검출하는 분류기를 만든다.
4. `detectMultiScale()` 의 `minNeighbors` 값을 크게 할수록 얼굴이 아닌 곳을 얼굴로 잘못 검출하는 일이 줄어든다.

## Q18 (객관식 · 2점)

`iris` 데이터프레임에는 숫자 열 4개(`sepal_length`, `sepal_width`, `petal_length`, `petal_width`)와 종 이름이 담긴 `species` 열이 있습니다. 다음 코드를 실행하면 그래프가 그려지는 칸(서브플롯)은 모두 몇 개입니까?

```python
sns.pairplot(iris, hue="species")
plt.show()
```

1. 4개
2. 6개
3. 12개
4. 16개

## Q19 (객관식 · 2점)

다음 코드에 대한 설명으로 옳지 **않은** 것은? `iris` 의 `species` 열에는 setosa, versicolor, virginica 세 가지 값이 들어 있습니다.

```python
g = sns.FacetGrid(iris, col="species", height=4, aspect=1)
g.map_dataframe(sns.histplot, x="sepal_length", kde=True)
g.set_titles(col_template="{col_name}")
plt.show()
```

1. `col="species"` 로 종마다 열을 나누므로 서브플롯 3개가 가로로 나란히 그려진다.
2. `height=4` 는 서브플롯 하나의 높이이고, `aspect=1` 이므로 서브플롯의 가로와 세로 길이가 같다.
3. `map_dataframe()` 에는 `sns.histplot()` 을 호출한 결과가 아니라 함수 이름 `sns.histplot` 을 넘긴다.
4. `set_titles(col_template="{col_name}")` 때문에 세 서브플롯의 제목이 모두 `species` 로 표시된다.

## Q20 (객관식 · 2점)

다음 코드를 실행했을 때 마지막 줄에서 출력되는 것은?

```python
import cv2

image = cv2.imread('photo.jpg')
print(image.shape[:2])        # (400, 600) 이 출력됨
resized = cv2.resize(image, (300, 200))
print(resized.shape[:2])
```

1. `(300, 200)`
2. `(200, 300)`
3. `(400, 600)`
4. `(600, 400)`

## Q21 (객관식 · 2점)

`image.shape[:2]` 가 `(300, 500)` 인 이미지를 회전하는 코드입니다. 설명으로 옳지 **않은** 것은?

```python
(h, w) = image.shape[:2]
center = (w // 2, h // 2)
M = cv2.getRotationMatrix2D(center, 45, 1.0)
rotated = cv2.warpAffine(image, M, (w, h))
```

1. `center` 의 값은 `(250, 150)` 이고, 회전의 중심이 되는 (x, y) 좌표이다.
2. 두 번째 인자 `45` 는 시계 방향으로 45도 회전하라는 뜻이고, 반시계 방향으로 돌리려면 음수를 준다.
3. 세 번째 인자 `1.0` 은 확대 비율이라서, 이 코드는 크기를 바꾸지 않고 회전만 한다.
4. `cv2.getRotationMatrix2D()` 는 변환 행렬을 만들기만 하고, 이미지를 실제로 변환하는 함수는 `cv2.warpAffine()` 이다.

## Q22 (객관식 · 2점)

얼굴 검출 프로그램에서 검출 결과를 이미지에 표시하는 부분입니다. `faces` 에 `(x, y, w, h)` 꼴의 검출 결과 `(40, 60, 100, 120)` 하나가 들어 있을 때, 실행 결과로 옳은 것은?

```python
for (x, y, w, h) in faces:
    cv2.rectangle(image, (x, y), (x + w, y + h), (255, 0, 0), 2)
```

1. 왼쪽 위 꼭짓점이 `(40, 60)`, 오른쪽 아래 꼭짓점이 `(100, 120)` 인 파란색 사각형이 두께 2 로 그려진다.
2. 왼쪽 위 꼭짓점이 `(40, 60)`, 오른쪽 아래 꼭짓점이 `(140, 180)` 인 빨간색 사각형이 두께 2 로 그려진다.
3. 왼쪽 위 꼭짓점이 `(40, 60)`, 오른쪽 아래 꼭짓점이 `(140, 180)` 인 파란색 사각형이 두께 2 로 그려진다.
4. 왼쪽 위 꼭짓점이 `(40, 60)`, 오른쪽 아래 꼭짓점이 `(100, 120)` 인 빨간색 사각형이 두께 2 로 그려진다.

## Q23 (객관식 · 2점)

동영상의 프레임마다 엣지를 검출해 보여 주는 프로그램입니다. 설명으로 옳지 **않은** 것은?

```python
import cv2

cap = cv2.VideoCapture("sample.mp4")
while True:
    ret, frame = cap.read()
    if not ret:
        break
    edges = cv2.Canny(frame, 100, 200)
    cv2.imshow('Edge Detection', edges)
    if cv2.waitKey(1) == ord('q'):
        break
cap.release()
cv2.destroyAllWindows()
```

1. 파일 경로 대신 `cv2.VideoCapture(0)` 으로 쓰면 컴퓨터의 기본 카메라(웹캠) 영상을 가져온다.
2. `cap.read()` 는 값 두 개를 돌려준다. `ret` 에는 프레임을 정상적으로 읽었는지를 나타내는 `True` 또는 `False` 가, `frame` 에는 읽은 프레임이 들어간다.
3. 동영상을 끝까지 읽어 더 읽을 프레임이 없으면 `ret` 이 `False` 가 되어 반복문을 빠져나온다.
4. `cv2.waitKey(1)` 은 키 입력을 1초 동안 기다린다는 뜻이고, `cv2.waitKey(0)` 은 기다리지 않고 바로 다음 줄로 넘어간다는 뜻이다.
5. `cv2.waitKey()` 는 누른 키의 아스키코드 값을 돌려주므로, `ord('q')` 와 비교해 q 키를 눌렀는지 확인한다.

## Q24 (객관식 · 2점)

이미지에서 녹색 부분만 남기는 코드입니다. `hsv` 에서 A 자리 픽셀의 값이 `(60, 200, 150)`, B 자리 픽셀의 값이 `(60, 50, 150)` 일 때 옳은 것은?

```python
green_lower = np.array([35, 100, 100])
green_upper = np.array([85, 255, 255])

hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
mask = cv2.inRange(hsv, green_lower, green_upper)
result = cv2.bitwise_and(image, image, mask=mask)
```

1. `mask` 의 값은 A 자리 255, B 자리 255 이고, `result` 의 두 자리는 `image` 와 같다.
2. `mask` 의 값은 A 자리 1, B 자리 0 이고, `result` 에서 B 자리는 검은색 `(0, 0, 0)` 이 된다.
3. `mask` 의 값은 A 자리 255, B 자리 0 이고, `result` 에서 B 자리는 검은색 `(0, 0, 0)` 이 된다.
4. `mask` 의 값은 A 자리 0, B 자리 255 이고, `result` 에서 A 자리는 검은색 `(0, 0, 0)` 이 된다.

## Q25 (객관식 · 2점)

붓꽃 데이터프레임 `iris` 로 그래프를 그리는 코드입니다. `species` 열에는 setosa, versicolor, virginica 세 가지 값이 들어 있습니다. 설명으로 옳지 **않은** 것은?

```python
sns.lmplot(data=iris,
           x="sepal_length",
           y="sepal_width",
           hue="species",
           height=6)
plt.title("Linear Regression Plot")
plt.show()
```

1. `lmplot` 의 lm 은 linear model 의 줄임말이다.
2. `sepal_length` 와 `sepal_width` 두 열의 산점도 위에 선형 회귀선이 함께 그려진다.
3. `hue="species"` 때문에 점의 색이 종마다 다르고, 회귀선도 종마다 하나씩 모두 3개 그려진다.
4. `height=6` 은 회귀선의 굵기를 6 으로 정한다.

## Q26 (객관식 · 2점)

사진에서 얼굴을 찾아 사각형으로 표시하는 프로그램입니다. (가), (나), (다)에 들어갈 것을 순서대로 바르게 적은 것은?

```python
import cv2

image = cv2.imread('people.jpg')
face_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
face_cascade = cv2.(가)(face_path)
gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
faces = face_cascade.(나)((다), scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
for (x, y, w, h) in faces:
    cv2.rectangle(image, (x, y), (x + w, y + h), (255, 0, 0), 2)
cv2.imshow('Face Detection', image)
cv2.waitKey(0)
cv2.destroyAllWindows()
```

1. (가) `detectMultiScale` (나) `CascadeClassifier` (다) `gray`
2. (가) `CascadeClassifier` (나) `detectMultiScale` (다) `gray`
3. (가) `CascadeClassifier` (나) `detectMultiScale` (다) `face_path`
4. (가) `CascadeClassifier` (나) `rectangle` (다) `gray`

## Q27 (객관식 · 2점)

웹캠 영상을 프레임마다 읽어 창에 보여 주고, q 키를 누르면 끝나는 프로그램입니다. (가), (나), (다)에 들어갈 이름을 순서대로 바르게 적은 것은?

```python
import cv2

cap = cv2.(가)(0)
while True:
    ret, frame = cap.(나)()
    if not ret:
        break
    cv2.imshow('Webcam', frame)
    if cv2.waitKey(1) == ord('q'):
        break
cap.(다)()
cv2.destroyAllWindows()
```

1. (가) `imread` (나) `read` (다) `release`
2. (가) `VideoCapture` (나) `imread` (다) `close`
3. (가) `VideoCapture` (나) `read` (다) `release`
4. (가) `videoCapture` (나) `read` (다) `release`

## Q28 (객관식 · 2점)

OpenCV 함수와 하는 일의 연결이 옳지 **않은** 것은?

1. `cv2.inRange()`: 이미지의 크기를 지정한 범위 안으로 줄인다.
2. `cv2.GaussianBlur()`: 노이즈를 줄이고 이미지를 부드럽게 만든다.
3. `cv2.warpAffine()`: 변환 행렬을 받아 이미지를 변환한다.
4. `cv2.destroyAllWindows()`: 화면에 띄운 창을 닫는다.

## Q29 (출력 예측 · 3점)

얼굴 검출 예제에서 사각형의 두 꼭짓점을 구하는 부분만 옮긴 코드입니다. `faces` 에는 `(x, y, w, h)` 꼴의 검출 결과 두 개가 들어 있습니다. 다음 코드의 출력 결과를 그대로 적으세요.

```python
faces = [(50, 30, 80, 100), (200, 40, 60, 70)]
for (x, y, w, h) in faces:
    pt1 = (x, y)
    pt2 = (x + w, y + h)
    print(pt1, pt2)
```

## Q30 (출력 예측 · 3점)

이미지 회전 예제에서 중심 좌표를 구하는 부분만 옮긴 코드입니다. `shape` 는 컬러 이미지의 `image.shape` 값입니다. 다음 코드의 출력 결과를 그대로 적으세요.

```python
shape = (480, 640, 3)
(h, w) = shape[:2]
center = (w // 2, h // 2)
print(h, w)
print(center)
print((w, h))
```

## Q31 (객관식 · 2점)

엣지 검출과 블러 처리 코드입니다. 설명으로 옳지 **않은** 것은?

```python
edges = cv2.Canny(image, 100, 200)
blurred = cv2.GaussianBlur(image, (15, 15), 0)
```

1. `cv2.Canny()` 의 100 은 최소 임계값, 200 은 최대 임계값이다.
2. `cv2.Canny()` 의 입력으로는 보통 그레이스케일 이미지를 쓴다.
3. `cv2.GaussianBlur()` 의 `(15, 15)` 는 커널 크기이고, 커널이 클수록 이미지가 더 선명해진다.
4. `cv2.GaussianBlur()` 의 마지막 인자 `0` 은 sigma 값을 OpenCV 가 자동으로 계산하게 한다.

## Q32 (단답 · 3점)

이미지에 가우시안 블러(Gaussian Blur) 필터를 적용해 노이즈를 줄이고 부드럽게 만든 뒤 화면에 보여 주는 프로그램입니다. 빈칸에 들어갈 함수 이름을 적으세요. 대소문자를 구분합니다.

```python
import cv2

image = cv2.imread('sample.jpg')
blurred = cv2.____(image, (15, 15), 0)
cv2.imshow('Gaussian Blur', blurred)
cv2.waitKey(0)
cv2.destroyAllWindows()
```

## Q33 (객관식 · 2점)

`edges = cv2.Canny(image, threshold1, threshold2)` 에 대한 설명으로 옳은 것은?

1. `threshold1`(최소 임계값)을 너무 낮게 정하면 원하지 않는 엣지까지 검출된다.
2. `threshold2`(최대 임계값)를 너무 높게 정하면 엣지가 더 많이 검출된다.
3. 두 임계값은 보통 `threshold1` 이 `threshold2` 의 2배나 3배가 되도록 정한다.
4. `cv2.Canny()` 는 검출한 엣지의 개수를 정수로 돌려준다.

## Q34 (객관식 · 2점)

붓꽃 종별 꽃받침 길이의 분포를 상자 그림과 커널 밀도 추정을 결합한 모양으로 그리고, 안쪽에 사분위수를 선으로 표시하려고 합니다. 빈칸에 들어갈 함수는?

```python
iris = sns.load_dataset("iris")
sns.____(data=iris, x="species", y="sepal_length", inner="quart")
plt.show()
```

1. `boxplot`
2. `violinplot`
3. `histplot`
4. `pairplot`

## Q35 (객관식 · 2점)

붓꽃 종별 꽃받침 길이의 히스토그램 위에 분포 곡선(커널 밀도 추정 곡선)을 함께 그리려고 합니다. 빈칸에 들어갈 인자는?

```python
iris = sns.load_dataset("iris")
sns.histplot(data=iris, x="sepal_length", hue="species", ____)
plt.title("Histogram Example")
plt.show()
```

1. `kde=True`
2. `curve=True`
3. `inner="quart"`
4. `style="kde"`

## Q36 (객관식 · 2점)

`cv2.imread()` 로 읽은 컬러 이미지 `image` 를 HSV 색 공간으로 변환하려고 합니다. 빈칸에 들어갈 플래그는?

```python
hsv = cv2.cvtColor(image, ____)
```

1. `cv2.COLOR_BGR2HSV`
2. `cv2.COLOR_HSV2BGR`
3. `cv2.COLOR_BGR2RGB`
4. `cv2.COLOR_BGR2GRAY`

## Q37 (객관식 · 2점)

이미지를 읽어 창에 보여 주는 프로그램입니다. 설명으로 옳은 것은?

```python
import cv2

image = cv2.imread('sample.jpg')
cv2.imshow('Loaded Image', image)
cv2.waitKey(0)
cv2.destroyAllWindows()
```

1. `cv2.imread()` 는 이미지 파일을 읽어 바로 새 창에 띄운다.
2. `cv2.imshow()` 의 첫 번째 인자 `'Loaded Image'` 는 창의 제목이고, 두 번째 인자가 보여 줄 이미지이다.
3. `cv2.waitKey(0)` 은 기다리지 않고 바로 다음 줄로 넘어간다.
4. `cv2.destroyAllWindows()` 는 읽어 온 이미지 파일 `sample.jpg` 를 지운다.

## Q38 (단답 · 3점)

산점도를 그리기 전에 색상 팔레트만 pastel 로 바꾸려고 합니다. 빈칸에 들어갈 Seaborn 함수 이름을 적으세요. 대소문자와 밑줄을 구분합니다.

```python
import seaborn as sns
import matplotlib.pyplot as plt

iris = sns.load_dataset("iris")
sns.____("pastel")
sns.scatterplot(data=iris, x="sepal_length", y="sepal_width", hue="species")
plt.title("Custom Palette")
plt.show()
```
