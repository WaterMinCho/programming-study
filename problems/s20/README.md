# 20차시 · Seaborn·OpenCV

강의 「딥러닝 파이썬 패키지(3)」의 내용으로, 통계 그래프를 그리는 Seaborn 과 이미지·영상을 처리하는 OpenCV 를 배우는 차시입니다.
두 패키지는 스터디 프로그램에서 실행해 볼 수 없어서 이 세트는 대부분 객관식과 단답으로 냅니다. 출력 예측 두 문항은 예제의 좌표 계산만 옮겨 패키지 없이 실행되는 코드입니다.
함수 이름의 철자와 대소문자, 인자의 순서와 뜻, 예제 코드의 흐름을 보고 답을 고를 수 있게 준비합니다.

| 강의 절 | 내용 |
|---|---|
| 1. seaborn 패키지(1) | 소개, 설치와 임포트, `load_dataset`, `set_theme`, 산점도·회귀선·히스토그램·상자 그림·바이올린 플롯·페어 플롯 |
| 2. seaborn 패키지(2) | `set_theme(style, palette)`, `set_palette`, `FacetGrid` 로 그리는 복합 그래프 |
| 3. opencv(1) | 소개, `imread`·`imshow`·`waitKey`, `resize`, `cvtColor`, 회전 |
| 4. opencv(2) | `Canny` 엣지 검출, `GaussianBlur` 블러 |
| 5. opencv(3) | `CascadeClassifier`·`detectMultiScale`·`rectangle` 로 하는 얼굴 검출 |
| 6. opencv(4) | `VideoCapture` 로 하는 영상 처리, `inRange`·`bitwise_and` 로 하는 색상 필터링 |

## 1. Seaborn 소개와 기본 설정

- Seaborn 은 파이썬의 데이터 시각화 라이브러리이고, 통계 그래프를 짧은 코드로 그립니다.
- Matplotlib 위에서 동작합니다. 그래서 제목은 `plt.title()`, 화면 표시는 `plt.show()` 로 합니다.
- 설치는 `pip install seaborn`, 불러올 때는 `import seaborn as sns` 입니다. 강의 코드는 `import matplotlib.pyplot as plt`, `import pandas as pd` 를 함께 적습니다.

```python
import seaborn as sns
import matplotlib.pyplot as plt

iris = sns.load_dataset("iris")           # 붓꽃 샘플 데이터를 데이터프레임으로 불러옴
sns.set_theme(style="whitegrid")          # 기본 스타일 설정
sns.scatterplot(data=iris,
                x="sepal_length",         # x 축: 꽃받침 길이
                y="sepal_width",          # y 축: 꽃받침 너비
                hue="species")            # 종마다 색을 다르게 함
plt.title("Iris Dataset")
plt.show()
```

- `iris` 의 열은 `sepal_length`(꽃받침 길이), `sepal_width`(꽃받침 너비), `petal_length`(꽃잎 길이), `petal_width`(꽃잎 너비), `species`(종)입니다. `species` 열에는 setosa, versicolor, virginica 가 들어 있습니다.
- `data` 에 데이터프레임을 넘기고 `x`, `y`, `hue` 에는 열 이름을 문자열로 적습니다. 따옴표를 빼면 그 이름의 변수를 찾다가 `NameError` 가 납니다.

## 2. 플롯 종류와 함수 이름

| 그래프 | 함수 | 보여 주는 것 | 강의 예제의 인자 |
|---|---|---|---|
| 산점도(Scatter Plot) | `sns.scatterplot()` | 두 변수 간의 관계 | `hue="species"`, `style="species"` |
| 선형 회귀선 | `sns.lmplot()` | 데이터의 선형적 관계 | `hue="species"`, `height=6` |
| 히스토그램(Histogram) | `sns.histplot()` | 데이터의 분포 | `x="sepal_length"`, `kde=True` |
| 상자 그림(Box Plot) | `sns.boxplot()` | 분포와 이상치 | `x="species"`, `y="sepal_length"` |
| 바이올린 플롯(Violin Plot) | `sns.violinplot()` | 상자 그림과 커널 밀도 추정을 결합한 분포 | `inner="quart"` |
| 페어 플롯(Pair Plot) | `sns.pairplot()` | 여러 변수 간의 관계를 한 번에 | `sns.pairplot(iris, hue="species")` |

- `hue` 는 색으로, `style` 은 점(마커)의 모양으로 범주를 나눕니다. 둘에 같은 열을 주면 종마다 색과 모양이 함께 달라집니다.
- `lmplot` 의 lm 은 linear model 입니다. 첫 글자는 소문자 엘(l)이고, `height` 는 그래프의 높이입니다. `hue="species"` 를 주면 점의 색이 종마다 달라지고 회귀선도 종마다 하나씩 그려집니다.
- `kde=True` 는 히스토그램 위에 커널 밀도 추정(KDE) 곡선, 곧 분포 곡선을 함께 그립니다.
- `inner="quart"` 는 바이올린 안쪽에 사분위수를 선으로 표시합니다.
- 페어 플롯은 숫자 열을 가로와 세로에 모두 놓습니다. `iris` 는 숫자 열이 4개라서 4 × 4 = 16칸이 그려지고, 대각선 4칸에는 각 변수의 분포가, 나머지 12칸에는 두 변수의 산점도가 들어갑니다.

강의의 `sns.boxplot(data=iris, x="species", y="sepal_length")` 는 x 축에 종을 놓고 종마다 상자를 하나씩 그린 그림입니다. 상자와 중앙선은 setosa(중앙값 5.0), versicolor(5.9), virginica(6.5) 순서로 높아집니다. 꽃받침 길이가 가장 긴 종은 virginica 이고, 근거는 상자 그림·바이올린 플롯·히스토그램에서 virginica 의 분포가 가장 큰 값 쪽에 있다는 점입니다. virginica 상자 아래에 따로 찍힌 점 하나는 이상치입니다.

과제는 난수로 만든 데이터의 히스토그램과 `tips` 데이터셋의 요일별 상자 그림을 요구합니다.

```python
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt

data = np.random.normal(50, 10, 1000)     # 평균 50, 표준편차 10 인 정규 분포 데이터 1000개
sns.histplot(data)
plt.show()

tips = sns.load_dataset("tips")
sns.boxplot(data=tips, x="day", y="total_bill")   # 요일별 전체 금액의 상자 그림
plt.show()
```

## 3. 스타일, 팔레트, 복합 그래프

- `sns.set_theme(style="darkgrid", palette="muted")` 처럼 `set_theme()` 으로 스타일과 팔레트를 함께 정합니다.
- `style` 에 쓰는 값은 `darkgrid`, `whitegrid`, `dark`, `white`, `ticks` 입니다.
- `palette` 에 쓰는 값은 `deep`, `muted`, `bright`, `pastel`, `dark`, `colorblind` 입니다.
- 색상 팔레트만 바꿀 때는 `sns.set_palette("pastel")` 을 씁니다.

`FacetGrid` 는 기준 열의 값마다 데이터를 나눠 서브플롯을 여러 개 만드는 클래스입니다.

```python
g = sns.FacetGrid(iris, col="species", height=4, aspect=1)     # 종마다 열을 나눔: 1행 3열
g.map_dataframe(sns.histplot, x="sepal_length", kde=True)      # 서브플롯마다 히스토그램을 그림
g.set_titles(col_template="{col_name}")                        # 제목: setosa, versicolor, virginica
plt.show()
```

- `row` 는 기준 열의 값마다 행을, `col` 은 열을 나눕니다. `col="species"` 는 가로로 3개, `row="species"` 는 세로로 3개를 그립니다.
- `height` 는 서브플롯 하나의 높이(인치)입니다. `width` 인자는 없고, 너비는 `aspect`(가로:세로 비율)로 정해집니다. `aspect=1.6` 이면 가로:세로가 1.6:1 입니다.
- `map_dataframe(func, x, kde)` 의 첫 인자에는 그릴 함수 이름을 괄호 없이 넘깁니다.
- `set_titles()` 의 `row_template` 은 행 제목, `col_template` 은 열 제목입니다. `"{col_name}"` 자리에 기준 열의 값이 들어갑니다.

## 4. OpenCV 소개와 이미지 읽기·보여 주기

- OpenCV(Open Source Computer Vision)는 실시간 컴퓨터 비전을 위한 라이브러리입니다. 파이썬을 포함한 여러 언어에서 쓸 수 있고 이미지와 영상 처리 기능을 제공합니다.
- 설치할 때의 이름은 `opencv-python`(`pip install opencv-python`)이고, 불러올 때의 이름은 `cv2`(`import cv2`)입니다. 슬라이드의 설치 명령에는 `pip install opencv-python==4.14.0.94` 처럼 버전이 붙어 있고 요약본에는 버전이 없습니다.

```python
import cv2

image = cv2.imread('./ch21/opencv/sample.jpg')   # 이미지 로드
cv2.imshow('Loaded Image', image)                # 창 제목, 보여 줄 이미지
cv2.waitKey(0)                                   # 키 입력을 기다림
cv2.destroyAllWindows()                          # 창을 닫음
```

- `cv2.imshow()` 의 첫 인자는 창의 제목이고 두 번째 인자가 이미지입니다.
- `cv2.waitKey(delay)` 의 `delay` 는 밀리초 단위입니다(1000 이 1초). `0` 은 키를 누를 때까지 시간 제한 없이 기다립니다. 반환값은 누른 키의 아스키코드 값입니다.

## 5. 크기 조정, 색 변환, 회전

```python
resized = cv2.resize(image, (300, 300))                  # dsize 는 (너비, 높이)
gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)           # 그레이스케일로 변환

(h, w) = image.shape[:2]                                 # shape 는 (높이, 너비) 순서
center = (w // 2, h // 2)                                # 회전 중심 (x, y)
M = cv2.getRotationMatrix2D(center, 45, 1.0)             # 중심, 각도, 확대 비율
rotated = cv2.warpAffine(image, M, (w, h))               # 행렬 M 으로 이미지를 변환
```

- `cv2.resize(src, dsize)` 의 `dsize` 는 `(width, height)` 튜플입니다. `image.shape[:2]` 는 `(높이, 너비)` 순서라서 두 순서가 서로 반대입니다.
- `cv2.cvtColor(src, code)` 의 `code` 는 변환 방법을 정하는 플래그입니다. 강의에 나온 플래그는 `cv2.COLOR_BGR2GRAY`, `cv2.COLOR_BGR2RGB`, `cv2.COLOR_BGR2HSV` 입니다. 이름은 `COLOR_원래색2바꿀색` 꼴이고 OpenCV 의 컬러 이미지는 B, G, R 순서입니다.
- `cv2.getRotationMatrix2D(center, angle, scale)` 은 2×3 변환 행렬(실수형)을 만듭니다. `angle` 은 도(degree) 단위이고 양수가 반시계 방향, 음수가 시계 방향입니다. `scale` 은 확대 비율입니다.
- `cv2.warpAffine(src, M, dsize)` 가 그 행렬로 이미지를 실제로 변환합니다. `dsize` 는 `(w, h)` 튜플이고 `(0, 0)` 을 주면 원본과 같은 크기가 됩니다.

## 6. 엣지 검출과 블러

```python
edges = cv2.Canny(image, 100, 200)                 # 최소 임계값 100, 최대 임계값 200
blurred = cv2.GaussianBlur(image, (15, 15), 0)     # 커널 크기 (15, 15), sigma 는 자동 계산
```

- `cv2.Canny(image, threshold1, threshold2)` 는 엣지 이미지를 돌려줍니다. 입력으로는 보통 그레이스케일 이미지를 씁니다.
- `threshold1` 은 최소 임계값입니다. 너무 낮으면 원하지 않는 엣지까지 검출됩니다. `threshold2` 는 최대 임계값이고 너무 높으면 엣지가 잘 검출되지 않습니다. 두 값은 보통 1:2 또는 1:3 비율로 정합니다.
- `cv2.GaussianBlur(src, ksize, sigmaX)` 는 노이즈를 줄이고 이미지를 부드럽게 만듭니다. 커널 크기 `ksize` 가 클수록 더 부드러워집니다. `ksize` 에 `(0, 0)` 을 주면 sigma 값으로 커널 크기가 정해지고, sigma 에 `0` 을 주면 OpenCV 가 값을 자동으로 계산합니다.

## 7. 얼굴 검출

```python
image = cv2.imread('./ch21/opencv/people.jpg')
face_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
face_cascade = cv2.CascadeClassifier(face_path)              # 사전 학습된 얼굴 검출기를 불러옴
gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
for (x, y, w, h) in faces:
    cv2.rectangle(image, (x, y), (x + w, y + h), (255, 0, 0), 2)
cv2.imshow('Face Detection', image)
cv2.waitKey(0)
cv2.destroyAllWindows()
```

- `cv2.CascadeClassifier(filename)` 은 Haar Cascade 분류기를 불러오는 클래스입니다. 학습된 XML 파일을 받아 객체를 만들고 얼굴, 눈, 차량 번호판 같은 객체 검출에 씁니다.
- `cv2.data.haarcascades` 는 모델 파일이 들어 있는 폴더 경로입니다. `haarcascade_frontalface_default.xml` 은 정면 얼굴용 모델이라 옆얼굴이나 회전된 얼굴에서는 정확도가 낮을 수 있습니다.
- `detectMultiScale()` 의 `scaleFactor` 는 1보다 커야 하고, 1.1 이면 이미지를 1.1배씩 줄여 가며 찾습니다. `minNeighbors` 는 값이 클수록 잘못된 검출이 줄어듭니다. `minSize=(30, 30)` 은 그보다 작은 얼굴을 무시합니다.
- 검출 결과는 `(x, y, w, h)` 사각형의 목록입니다. 검출은 그레이스케일 `gray` 에서 하고 사각형은 원본 `image` 에 그립니다.
- `cv2.rectangle(img, pt1, pt2, color, thickness)` 의 `pt1` 은 왼쪽 위 꼭짓점 `(x, y)`, `pt2` 는 오른쪽 아래 꼭짓점 `(x + w, y + h)` 입니다. `color` 는 `(B, G, R)` 순서라서 `(255, 0, 0)` 은 파란색입니다. `thickness` 는 선 두께이고 기본값은 1, 음수를 주면 안쪽을 채웁니다.

## 8. 영상 처리와 색상 필터링

```python
# cap = cv2.VideoCapture(0)                        # 웹캠을 쓸 때
cap = cv2.VideoCapture("./ch21/opencv/sample.mp4")
while True:
    ret, frame = cap.read()                        # (성공 여부, 프레임)
    if not ret:                                    # 더 읽을 프레임이 없으면 끝냄
        break
    edges = cv2.Canny(frame, 100, 200)
    cv2.imshow('Edge Detection', edges)
    if cv2.waitKey(1) == ord('q'):                 # 1밀리초 기다리고, q 를 눌렀으면 끝냄
        break
cap.release()                                      # 쓰던 자원을 반환
cv2.destroyAllWindows()
```

- `cv2.VideoCapture(index)` 에 `0` 을 넘기면 컴퓨터의 기본 카메라를 엽니다. 카메라가 두 대면 0 또는 1 입니다. 동영상 파일은 경로를 문자열로 넘깁니다.
- `read()` 는 값 두 개를 돌려줍니다. 프레임을 정상적으로 읽으면 첫 번째 값이 `True`, 실패하면 `False` 입니다.
- `ord('q')` 는 q 의 아스키코드 값(113)입니다. `cv2.waitKey()` 가 돌려준 값과 비교해 q 키를 눌렀는지 확인합니다.

```python
green_lower = np.array([35, 100, 100])
green_upper = np.array([85, 255, 255])

hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)                # HSV 색 공간으로 변환
mask = cv2.inRange(hsv, green_lower, green_upper)           # 범위 안은 255, 나머지는 0
result = cv2.bitwise_and(image, image, mask=mask)           # 마스크가 255 인 곳만 남김
```

- `cv2.inRange(src, lowerb, upperb)` 는 입력과 크기가 같은 마스크를 돌려줍니다. 세 값이 모두 하한과 상한 사이에 있는 픽셀은 255, 나머지는 0 입니다.
- `cv2.bitwise_and(src1, src2, mask)` 는 마스크가 정한 영역만 남깁니다. 마스크가 0 인 자리는 검은색이 됩니다.

## 시험에서 헷갈리기 쉬운 점

- 설치 이름과 임포트 이름을 구분합니다. Seaborn 은 `pip install seaborn` 과 `import seaborn as sns`, OpenCV 는 `pip install opencv-python` 과 `import cv2` 입니다. `import opencv` 는 오류입니다.
- 함수 이름은 대소문자까지 맞아야 합니다. `cvtColor`, `waitKey`, `destroyAllWindows`, `Canny`, `GaussianBlur`, `VideoCapture`, `CascadeClassifier`, `detectMultiScale`, `inRange`, `getRotationMatrix2D`, `warpAffine` 은 중간이나 첫 글자에 대문자가 있고, `imread`, `imshow`, `resize`, `rectangle`, `bitwise_and` 는 모두 소문자입니다.
- Seaborn 의 그래프 함수는 모두 소문자이고 `plot` 으로 끝납니다(`scatterplot`, `lmplot`, `histplot`, `boxplot`, `violinplot`, `pairplot`). `sns.hist`, `sns.box` 같은 이름은 없습니다. `plt.hist()`, `plt.boxplot()` 은 18차시에 배운 Matplotlib 의 함수입니다.
- `lmplot` 은 소문자 엘로 시작합니다. 요약본의 소제목에는 `Implot`(대문자 아이)으로 적혀 있지만 코드의 함수 이름은 `sns.lmplot` 입니다.
- `FacetGrid` 는 F 와 G 가 대문자입니다. `load_dataset`, `set_theme`, `set_palette`, `map_dataframe`, `set_titles` 는 소문자와 밑줄로 씁니다. `load_dataset` 끝에는 s 가 없고 `set_titles` 끝에는 s 가 있습니다.
- `hue` 는 색, `style` 은 마커 모양입니다. `scatterplot` 의 `style` 인자와 `set_theme` 의 `style` 인자는 이름만 같고 하는 일은 서로 관계가 없습니다.
- `darkgrid`, `whitegrid`, `dark`, `white`, `ticks` 는 스타일 이름이고 `deep`, `muted`, `bright`, `pastel`, `dark`, `colorblind` 는 팔레트 이름입니다. `dark` 만 양쪽에 다 있습니다.
- 두 변수의 관계는 산점도, 분포는 히스토그램, 분포와 이상치는 상자 그림, 여러 변수의 관계를 한 번에 보는 것은 페어 플롯입니다.
- sepal 은 꽃받침, petal 은 꽃잎입니다. 슬라이드의 `lmplot` 설명과 요약본의 산점도 설명에는 꽃잎이라고 적혀 있지만 코드의 열 이름은 `sepal_length`, `sepal_width`(꽃받침)입니다. 문제에서는 코드에 적힌 열 이름을 따릅니다.
- `cv2.resize()` 의 크기는 `(너비, 높이)`, `image.shape[:2]` 는 `(높이, 너비)` 입니다. `cv2.resize(image, (300, 200))` 의 결과는 `shape[:2]` 가 `(200, 300)` 입니다.
- 회전 중심은 `(w // 2, h // 2)` 로 x 좌표(너비 쪽)를 먼저 적습니다. 각도는 양수가 반시계 방향입니다.
- 그레이스케일 플래그는 `cv2.COLOR_BGR2GRAY` 입니다. `GRAY` 의 철자가 A 이고, B, G, R 순서로 적습니다.
- `(255, 0, 0)` 은 OpenCV 에서 파란색입니다. 빨간색은 `(0, 0, 255)` 입니다.
- 사각형의 두 번째 좌표는 너비와 높이가 아니라 오른쪽 아래 꼭짓점 `(x + w, y + h)` 입니다.
- `cv2.waitKey(0)` 은 0초가 아니라 키를 누를 때까지 기다립니다. `cv2.waitKey(1)` 은 1초가 아니라 1밀리초입니다.
- `cap.read()` 가 돌려주는 값의 순서는 성공 여부가 먼저, 프레임이 나중입니다.
- Canny 의 임계값은 앞이 최소, 뒤가 최대입니다. `GaussianBlur` 의 마지막 `0` 은 블러를 끄는 값이 아니라 sigma 를 자동으로 계산하게 하는 값입니다.
- `inRange` 가 만드는 마스크의 값은 `True`/`False` 나 1/0 이 아니라 255/0 입니다.
- `minNeighbors` 는 값이 클수록 잘못된 검출이 줄어듭니다. `scaleFactor` 는 1보다 커야 합니다.
