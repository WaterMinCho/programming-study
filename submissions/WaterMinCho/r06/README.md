# 6회차 미니 모의고사

> 프로그램(`python study.py`)에서 풀면 이 폴더의 `quiz.py` 와 `.py` 파일에 답이 자동으로 저장됩니다.

문항 18개(보강할 단원 11개) · 평균 레벨 1.9 · 단원: s10 3, s03 2, s05 2, s12 2, s19 2, s20 2, s04 1, s08 1, s09 1, s16 1, s18 1

## s03_Q1 (조건식과 제어문 · 단답 · 3점)

비교 연산의 결과처럼 `True` 또는 `False` 값만 갖는 자료형이 있습니다.
다음 코드를 실행하면 `<class '____'>` 형태로 출력되는데, 빈칸에 들어갈 자료형 이름을 적으세요.

```python
print(type(3 > 1))
```

## s03_Q3 (조건식과 제어문 · 객관식 · 2점)

다음 중 출력 결과가 나머지 셋과 **다른** 하나는?

1. `print(True and False)`
2. `print(False or False)`
3. `print(not True)`
4. `print(False or True)`

## s05_Q3 (반복문 · 객관식 · 2점)

다음 코드를 실행했더니 아래와 같이 출력되었습니다. 빈칸(`____`)에 들어갈 조건으로 알맞은 것은?

```python
count = 5
while ____:
    count -= 1
    print(count)
```

```
4
3
2
```

1. `count > 2`
2. `count >= 2`
3. `count > 3`
4. `count != 3`

## s05_Q5 (반복문 · 객관식 · 2점)

다음 코드를 실행했을 때 출력되는 것은?

```python
for n in range(1, 5):
    total = 0
    total = total + n
print(total)
```

1. `10`
2. `4`
3. `0`
4. 오류가 발생한다

## s08_Q15 (자료구조와 알고리즘 · 출력 예측 · 3점)

다음 코드의 출력 결과를 그대로 적으세요.

```python
def fch(x):
    x["kim"] = 95
    x["park"] = 70

score = {"kim": 80, "lee": 90}
backup = score
fch(backup)
print(score)
print(len(score))
```

## s10_Q7 (클래스(2) · 객관식 · 2점)

다음 코드에 대한 설명으로 옳지 **않은** 것은?

```python
class Printer:
    def start(self):
        print("전원 켜짐")

    def info(self):
        print("일반 프린터")


class ColorPrinter(Printer):
    def info(self):
        print("컬러 프린터")

    def scan(self):
        print("스캔 중")
```

1. `ColorPrinter` 객체는 `start()` 를 직접 정의하지 않았지만 부모에게서 물려받았으므로 호출할 수 있다.
2. `ColorPrinter` 에서 `info()` 를 같은 이름으로 다시 정의한 것을 오버라이딩이라고 한다.
3. `ColorPrinter()` 객체의 `info()` 를 호출하면 `컬러 프린터` 가 출력된다.
4. `Printer()` 객체도 `scan()` 을 호출할 수 있다.

## s18_Q28 (Pandas·NumPy·Matplotlib · 객관식 · 2점)

`df` 는 CSV 파일을 pandas 로 불러와 만든 DataFrame 이고, 2016년부터 2024년까지의 `연도` 열과 그 해의 `영치대수` 열이 있습니다. `import matplotlib.pyplot as plt` 를 한 상태에서, 가로축이 연도이고 세로축이 영치대수인 **선 그래프**를 그리는 코드는?

1. `plt.plot(df['연도'], df['영치대수'])`
2. `plt.plot(df['영치대수'], df['연도'])`
3. `plt.bar(df['연도'], df['영치대수'])`
4. `plt.scatter(df['연도'], df['영치대수'])`

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

## s19_Q28 (statsmodels·scikit-learn·SciPy · 객관식 · 2점)

선형 회귀 요약표(OLS Regression Results)의 항목에 대한 설명으로 옳지 **않은** 것은?

1. `R-squared` 는 결정 계수이고 0 에서 1 사이의 값이며, 1 에 가까울수록 모델이 데이터를 잘 설명한다.
2. `Adj. R-squared` 는 독립변수가 늘면 결정 계수가 커지는 문제를 독립변수의 개수와 표본 크기로 조정한 값이다.
3. `F-statistic` 은 회귀모델 전체가 통계적으로 유의한지 보는 값이고, 값이 작을수록 유의하다고 판단한다.
4. `std err` 는 계수 추정치의 표준오차이고 값이 작을수록 좋다.

## s20_Q15 (Seaborn·OpenCV · 단답 · 3점)

컬러 이미지를 흑백(그레이스케일)으로 변환해 화면에 보여 주는 프로그램입니다. 빈칸에 들어갈 함수 이름을 적으세요. 대소문자를 구분합니다.

```python
import cv2

image = cv2.imread('color.jpg')
gray = cv2.____(image, cv2.COLOR_BGR2GRAY)
cv2.imshow('Grayscale Image', gray)
cv2.waitKey(0)
cv2.destroyAllWindows()
```

## s20_Q16 (Seaborn·OpenCV · 단답 · 3점)

이미지에서 엣지(윤곽선)를 검출해 화면에 보여 주는 프로그램입니다. 빈칸에 들어갈 함수 이름을 적으세요. 대소문자를 구분합니다.

```python
import cv2

image = cv2.imread('sample.jpg')
edges = cv2.____(image, 100, 200)
cv2.imshow('Edge Detection', edges)
cv2.waitKey(0)
cv2.destroyAllWindows()
```

## s04_p11 (리스트와 딕셔너리 · 반환값 · 좌표 옮기기 · 6점)

파일: `s04_p11.py`

로봇의 현재 위치가 튜플 `pos` 에 `(x, y)` 순서로, 이동할 거리가 튜플 `move` 에 `(dx, dy)` 순서로 주어집니다.
이동한 뒤의 위치 `(x + dx, y + dy)` 를 **튜플**로 반환하는 `solution` 함수를 완성하세요.

- 함수 이름과 매개변수는 바꾸지 않습니다.
- 반환값의 자료형은 튜플이어야 합니다. 값이 같아도 리스트 `[4, 6]` 은 오답입니다.

## 제한 사항
- `pos`, `move` 는 정수 2개로 된 튜플
- 각 정수는 -1000 이상 1000 이하

## 입출력 예

| pos | move | 반환값 |
|---|---|---|
| `(1, 2)` | `(3, 4)` | `(4, 6)` |
| `(0, 0)` | `(-2, 5)` | `(-2, 5)` |
| `(10, -3)` | `(0, 0)` | `(10, -3)` |

## s09_p11 (클래스(1) · 빈칸 채우기 · 게임 캐릭터 체력 · 6점)

파일: `s09_p11.py`

체력(`hp`)을 관리하는 `Hero` 클래스입니다. 빈칸(`____`) 3곳을 채워 클래스를 완성하세요.

- `hit(damage)` 는 체력을 `damage` 만큼 줄입니다. 체력이 0 보다 작아지면 **0 으로** 맞춥니다.
- `alive()` 는 체력이 0 보다 크면 `True`, 아니면 `False` 를 **반환**합니다.
- `heal(amount)` 는 **살아 있을 때만**(`alive()` 가 `True` 일 때만) 체력을 `amount` 만큼 늘립니다. 체력이 0 인 캐릭터는 회복되지 않습니다.
- **빈칸만** 채웁니다. 다른 줄을 고치거나 줄을 추가하면 오답 처리됩니다.

## 테스트 코드와 출력 예

```python
h = Hero("기사", 10)
h.hit(4)
print(h.hp)
h.heal(3)
print(h.hp)
h.hit(20)
print(h.hp, h.alive())
h.heal(5)
print(h.hp)
```

```
6
9
0 False
0
```

```python
h = Hero("궁수", 5)
print(h.alive())
h.hit(5)
print(h.hp, h.alive())
```

```
True
0 False
```

## 시작 코드

```python
class Hero:
    def __init__(self, name, hp):
        self.name = name
        self.hp = hp

    def hit(self, damage):
        self.hp = self.hp - damage
        if self.hp < 0:
            ____ = 0

    def alive(self):
        return ____ > 0

    def heal(self, amount):
        if self.____():
            self.hp = self.hp + amount
```

## s10_p10 (클래스(2) · 출력 · 긴급 안내 방송 · 6점)

파일: `s10_p10.py`

아래 `Announcer` 클래스가 이미 작성되어 있습니다(시작 코드에 포함).

```python
class Announcer:
    def __init__(self, place):
        self.place = place

    def prefix(self):
        return "[안내]"

    def say(self, text):
        print(self.prefix() + " " + self.place + ": " + text)
```

`Announcer` 를 **상속받는** `EmergencyAnnouncer` 클래스를 정의하세요.

- `prefix()` 메서드만 **재정의(오버라이딩)** 하여 문자열 `[긴급]` 을 **반환**합니다.
- `__init__` 과 `say()` 는 새로 만들지 않습니다. 부모의 것을 그대로 씁니다.
- `Announcer` 클래스는 고치지 않습니다. 채점할 때는 아래와 같은 테스트 코드가 객체를 만들어 메서드를 호출합니다.

## 테스트 코드와 출력 예

```python
e = EmergencyAnnouncer("3층")
e.say("대피하세요")
```

```
[긴급] 3층: 대피하세요
```

```python
a = Announcer("로비")
a.say("환영합니다")
e = EmergencyAnnouncer("로비")
e.say("환영합니다")
```

```
[안내] 로비: 환영합니다
[긴급] 로비: 환영합니다
```

- 출력은 글자 하나까지 같아야 합니다. 대괄호 뒤 공백 한 칸, 장소 뒤 콜론과 공백 한 칸입니다.

## s10_p12 (클래스(2) · 출력 · 카운터 변형 · 6점)

파일: `s10_p12.py`

아래 `Counter` 클래스가 이미 작성되어 있습니다(시작 코드에 포함).

```python
class Counter:
    def __init__(self):
        self.value = 0

    def up(self):
        self.value = self.value + 1

    def show(self):
        print("현재 값:", self.value)
```

`Counter` 를 **상속받는** 두 클래스를 정의하세요.

| 클래스 | 설명 |
|---|---|
| `DoubleCounter(Counter)` | `up()` 을 **재정의**해 한 번 호출할 때 `value` 가 `2` 커지게 합니다. `__init__` 은 새로 만들지 않습니다. |
| `StepCounter(Counter)` | 생성자 `StepCounter(step)` 는 **부모의 `__init__`** 으로 `value` 를 `0` 으로 만든 뒤, `step` 을 인스턴스 변수 `step` 에 저장합니다. `up()` 을 **재정의**해 한 번 호출할 때 `value` 가 `step` 만큼 커지게 합니다. |

- `show()` 는 두 클래스 모두 재정의하지 않습니다.
- `Counter` 클래스는 고치지 않습니다. 채점할 때는 아래와 같은 테스트 코드가 객체를 만들어 메서드를 호출합니다.

## 테스트 코드와 출력 예

```python
d = DoubleCounter()
d.up()
d.up()
d.show()
```

```
현재 값: 4
```

```python
s = StepCounter(5)
s.up()
s.up()
s.up()
s.show()
```

```
현재 값: 15
```

```python
c = Counter()
d = DoubleCounter()
s = StepCounter(10)
c.up()
d.up()
s.up()
print(c.value, d.value, s.value)
```

```
1 2 10
```

## 제한 사항
- `step` 은 1 이상 100 이하의 정수

## s12_p03 (파일 처리 · 빈칸 채우기 · 명단 출력하기 · 6점)

파일: `s12_p03.py`

현재 폴더에 이름이 한 줄에 하나씩 적힌 `names.txt` 가 있습니다. 파일의 모든 줄을 리스트로 읽어 인원 수를 출력한 뒤, 이름을 한 줄에 하나씩 출력하는 프로그램입니다.
빈칸(`____`) 3곳을 채워 프로그램을 완성하세요.

- 첫 줄에 `인원: 3` 처럼 줄 수를 출력합니다. (`인원:` 뒤에 공백 한 칸)
- 그다음 줄부터 파일에 적힌 순서대로 이름을 출력합니다. 읽은 줄에는 줄바꿈 문자가 이미 들어 있으므로, 이름 사이에 빈 줄이 생기지 않게 출력해야 합니다.
- 빈칸만 채웁니다. 다른 줄을 고치거나 줄을 추가하면 오답 처리됩니다.

```python
with open("names.txt", "r", encoding="utf-8") as f:
    lines = f.____()

print("인원:", ____(lines))
for line in lines:
    print(line, end=____)
```

## 입출력 예

`names.txt` 의 내용이 다음과 같을 때

```
민수
지영
현우
```

출력

```
인원: 3
민수
지영
현우
```

## s12_p05 (파일 처리 · 반환값 · 파일 속 숫자 합계 · 6점)

파일: `s12_p05.py`

한 줄에 정수가 하나씩 적힌 텍스트 파일의 경로 `path` 가 주어질 때, 파일에 적힌 모든 정수의 합을 정수로 **반환(return)** 하는 `solution` 함수를 완성하세요.

- 파일은 현재 폴더에 이미 만들어져 있습니다.
- 각 줄에는 정수 하나만 있고, 음수가 있을 수 있습니다. 마지막 줄 끝에 줄바꿈이 없을 수도 있습니다.
- 빈 파일이면 `0` 을 반환합니다.
- 읽은 줄은 문자열이므로 `int()` 로 바꿔서 더합니다. `int()` 는 문자열 앞뒤의 공백·줄바꿈을 무시하고 변환합니다. (`int("10\n")` → `10`)
- 함수 이름과 매개변수는 바꾸지 않습니다.

## 입출력 예

| 호출 | 파일 내용 | 반환값 |
|---|---|---|
| `solution("n.txt")` | `10`⏎`20`⏎`30`⏎ | `60` |
| `solution("n.txt")` | `5` | `5` |
| `solution("n.txt")` | `-3`⏎`3`⏎ | `0` |

(⏎ 는 줄바꿈을 뜻합니다)

## s16_p11 (알고리즘(1) · 반환값 · 동아리 가입 현황 · 6점)

파일: `s16_p11.py`

로봇 동아리 가입자의 학번이 담긴 세트 `robot` 과 코딩 동아리 가입자의 학번이 담긴 세트 `coding` 이 주어집니다.
아래 세 값을 순서대로 담은 **리스트**를 반환하는 `solution` 함수를 완성하세요.

1. 두 동아리에 모두 가입한 학생 수
2. 한 곳 이상 가입한 학생 수(두 곳에 모두 가입한 학생은 한 번만 셉니다)
3. 정확히 한 곳에만 가입한 학생 수

- 함수 이름과 매개변수는 바꾸지 않습니다. `print` 가 아니라 `return` 으로 돌려줍니다.
- 반환값은 정수 3개가 든 리스트입니다(튜플이나 세트는 오답).

## 제한 사항
- 각 세트의 요소는 1 이상 1000 이하의 정수이고, 세트마다 요소가 1개 이상 100개 이하입니다.

## 입출력 예

| robot | coding | 반환값 |
|---|---|---|
| `{1, 2, 3}` | `{3, 4}` | `[1, 4, 3]` |
| `{5, 7}` | `{5, 7}` | `[2, 2, 0]` |
| `{1, 2}` | `{8, 9, 10}` | `[0, 5, 5]` |

첫 번째 예: 두 곳 모두 가입한 학생은 3번 한 명, 한 곳 이상 가입한 학생은 1·2·3·4번 네 명, 한 곳에만 가입한 학생은 1·2·4번 세 명입니다.

