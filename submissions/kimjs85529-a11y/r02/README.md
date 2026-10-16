# 2회차 미니 모의고사

> 프로그램(`python study.py`)에서 풀면 이 폴더의 `quiz.py` 와 `.py` 파일에 답이 자동으로 저장됩니다.

문항 18개(보강할 단원 20개) · 평균 레벨 1.4 · 단원: s14 3, s01 2, s08 2, s09 2, s02 1, s03 1, s07 1, s10 1, s11 1, s13 1, s17 1, s20 1, s21 1

## s01_Q23 (파이썬 소개 및 환경설정 · 객관식 · 2점)

VSCode 를 설치한 직후이고, 확장(Extensions)은 아직 하나도 설치하지 않았습니다. 이 상태에서 할 수 **없는** 것은?

1. 탐색기 영역에서 새 폴더와 새 파일을 만든다.
2. 텍스트 에디터 영역에 코드를 작성하고 저장한다.
3. `Ctrl + ~` 로 터미널을 연다.
4. 메뉴를 한국어로 바꿔서 본다.

## s02_Q17 (프로그래밍 기초 · 객관식 · 2점)

다음 코드에 대한 설명으로 옳지 **않은** 것은?

```python
price = 1200
total = price * 3
```

1. 첫째 줄에서 대입 연산자 왼쪽의 `price` 는 l_value, 오른쪽의 `1200` 은 r_value 이다.
2. 둘째 줄의 `price` 는 대입 연산자 오른쪽에 있으므로 저장된 값 `1200` 으로 해석된다.
3. 둘째 줄은 `price * 3` 을 먼저 계산한 뒤 그 결과를 `total` 에 저장한다.
4. 둘째 줄을 실행하고 나면 `price` 에 저장된 값도 `3600` 으로 바뀐다.
5. 둘째 줄을 실행하고 나면 `total` 은 정수형 변수이다.

## s03_Q3 (조건식과 제어문 · 객관식 · 2점)

다음 중 출력 결과가 나머지 셋과 **다른** 하나는?

1. `print(True and False)`
2. `print(False or False)`
3. `print(not True)`
4. `print(False or True)`

## s08_Q3 (자료구조와 알고리즘 · 출력 예측 · 3점)

다음 코드의 출력 결과를 그대로 적으세요.

```python
def swap_a(na, nb):
    temp = na
    na = nb
    nb = temp

def swap_b(cb):
    temp = cb[0]
    cb[0] = cb[1]
    cb[1] = temp

ca = [5, 9]
swap_a(ca[0], ca[1])
print(ca)
swap_b(ca)
print(ca)
```

## s08_Q13 (자료구조와 알고리즘 · 객관식 · 2점)

다음은 최솟값의 위치만 변수 `pos` 에 기억하는 방식으로 쓴 선택 정렬입니다.
`[10, 15, 20, 30, 40]` 이 출력되도록(오름차순 정렬) 빈칸에 들어갈 조건식은?

```python
def sel_sort(nums):
    for i in range(len(nums)):
        pos = i
        for j in range(i + 1, len(nums)):
            if ____:
                pos = j
        nums[i], nums[pos] = nums[pos], nums[i]
    return nums

print(sel_sort([30, 10, 40, 20, 15]))
```

1. `nums[j] < nums[i]`
2. `nums[j] > nums[pos]`
3. `nums[i] < nums[j]`
4. `nums[j] < nums[pos]`

## s09_Q14 (클래스(1) · 단답 · 3점)

객체를 생성할 때 자동으로 호출되어 객체를 초기화하는 메서드의 이름을 적으세요. (괄호와 매개변수는 빼고 이름만)

## s13_Q19 (예외 처리·문자열·람다·map · 출력 예측 · 3점)

다음 코드의 출력 결과를 그대로 적으세요.

```python
codes = ["12", "ab", "0", "7"]
ok = 0
for c in codes:
    try:
        n = 100 // int(c)
    except (ValueError, ZeroDivisionError):
        print("건너뜀:", c)
        continue
    ok = ok + 1
    print(n)
print("성공", ok, "건")
```

## s14_Q24 (정규표현식 · 객관식 · 2점)

정규식 `^abc` 의 의미로 옳은 것은?

1. 문자열이 `abc` 로 시작해야 매치된다.
2. 문자열이 `abc` 로 끝나야 매치된다.
3. 문자열 어디에든 `abc` 가 들어 있으면 매치된다.
4. `a`, `b`, `c` 가 아닌 글자 하나와 매치된다.

## s14_Q28 (정규표현식 · 객관식 · 2점)

정규표현식과 `re` 모듈에 대한 설명으로 옳지 **않은** 것은?

1. 정규표현식은 정해 둔 패턴으로 문자열을 검색하거나 일치 여부를 확인하고, 필요한 부분을 추출·변환하는 데 쓴다.
2. 이메일·전화번호 형식 검증이나 로그 파일 처리에 쓰이며, 문법이 언어 사이에 비슷해 다른 언어에서도 응용할 수 있다.
3. `re.compile(정규식)` 은 정규식을 컴파일한 패턴 객체를 돌려주고, 이 객체의 `match`, `search`, `findall`, `finditer` 로 문자열을 조사한다.
4. 축약형 `re.match(정규식, 문자열)` 은 match 객체가 아니라 매치된 문자열을 바로 돌려준다.

## s17_Q2 (알고리즘(2) · 객관식 · 2점)

도시를 노드로, 도로를 엣지로 두고 도로마다 이동하는 데 걸리는 시간을 적어 둔 그래프가 있습니다.
이처럼 엣지에 비용이나 시간 같은 값을 붙인 그래프를 무엇이라고 하는가?

1. 무방향 그래프(undirected graph)
2. 방향 그래프(directed graph)
3. 가중 그래프(weighted graph)
4. 인접 그래프(adjacent graph)

## s20_Q3 (Seaborn·OpenCV · 객관식 · 2점)

Seaborn 에서 두 변수 간의 관계를 시각적으로 표현하기 위해 사용하는 함수는?

1. `sns.distplot()`
2. `sns.histplot()`
3. `sns.violinplot()`
4. `sns.scatterplot()`

## s01_p02 (파이썬 소개 및 환경설정 · 빈칸 채우기 · 보이는 그대로 출력하기 · 4점)

파일: `s01_p02.py`

아래 **출력 예**의 두 줄이 그대로 출력되도록 빈칸(`____`)을 채워 프로그램을 완성하세요.

- **빈칸만** 채웁니다. 다른 부분을 고치거나 줄을 추가하면 오답 처리됩니다.
- 출력은 글자 하나까지 같아야 합니다(띄어쓰기, 쉼표, 느낌표, 대소문자 포함).

## 시작 코드

```python
print(____)
print(____)
```

## 출력 예

```
7 + 8
Hello, Python!
```

## s07_p08 (함수(2) · 반환값 · 평균 이상인 점수의 개수 · 6점)

파일: `s07_p08.py`

점수가 담긴 리스트 `scores` 가 주어질 때, **평균 이상인 점수가 몇 개인지** 반환하는 `solution` 함수를 완성하세요.

- 평균은 (모든 점수의 합) ÷ (점수의 개수) 입니다. 평균은 소수가 될 수 있습니다.
- 평균과 같은 점수도 "평균 이상"에 포함합니다.
- 평균을 구하는 부분을 별도의 함수로 정의하고 `solution` 안에서 호출해도 좋습니다.
- 함수 이름 `solution` 과 매개변수는 바꾸지 않습니다.

## 제한 사항
- 1 ≤ scores 의 길이 ≤ 100
- 0 ≤ 각 점수 ≤ 100 (정수)

## 입출력 예

| scores | 반환값 | 설명 |
|---|---|---|
| `[10, 20, 30, 40, 50]` | 3 | 평균은 30. 평균 이상인 점수는 30, 40, 50 |
| `[90, 80, 100, 60]` | 2 | 평균은 82.5. 평균 이상인 점수는 90, 100 |
| `[70, 70, 70]` | 3 | 평균은 70. 세 점수 모두 평균과 같음 |

## s09_p07 (클래스(1) · 빈칸 채우기 · 물탱크 채우기 · 6점)

파일: `s09_p07.py`

물의 양(`level`)을 관리하는 `Tank` 클래스입니다. 빈칸(`____`) 3곳을 채워 클래스를 완성하세요.

- 객체를 만들면 `level` 은 0 입니다.
- `fill(amount)` 은 `level` 을 `amount` 만큼 늘립니다. **인수 없이** `fill()` 로 호출하면 `10` 만큼 늘립니다.
- `fill_twice(amount)` 는 같은 객체의 `fill` 메서드를 **두 번** 호출해서 `amount` 만큼씩 두 번 채웁니다.
- **빈칸만** 채웁니다. 다른 줄을 고치거나 줄을 추가하면 오답 처리됩니다.

## 테스트 코드와 출력 예

```python
t = Tank()
t.fill()
print(t.level)
t.fill(5)
print(t.level)
t.fill_twice(20)
print(t.level)
```

```
10
15
55
```

## 시작 코드

```python
class Tank:
    def __init__(self):
        self.level = 0

    def fill(self, amount=____):
        self.level = self.level + amount

    def fill_twice(self, amount):
        ____.fill(amount)
        self.____(amount)
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

## s11_p02 (GUI 프로그래밍(PyQt6 · tkinter) · 빈칸 채우기 · 체크박스 흉내 · 4점)

파일: `s11_p02.py`

PyQt6 의 `QCheckBox` 가 하는 일을 GUI 없이 흉내 낸 `CheckBox` 클래스입니다. 빈칸(`____`) 3곳을 채워 완성하세요.

- 객체를 만들면 글자(`text`)를 저장하고, 선택되지 않은 상태로 시작합니다.
- `setChecked(value)` 는 선택 상태를 전달받은 값(`True`/`False`)으로 바꿉니다.
- `isChecked()` 는 현재 선택 상태를 `True` 또는 `False` 로 반환합니다.
- 빈칸만 채웁니다. 다른 줄을 고치거나 줄을 추가하면 오답 처리됩니다.

```python
class CheckBox:
    def __init__(self, text):
        self.text = text
        self.checked = ____

    def setChecked(self, value):
        self.checked = ____

    def isChecked(self):
        return ____
```

## 테스트 코드와 출력 예

```python
c = CheckBox("라떼")
print(c.isChecked())
c.setChecked(True)
print(c.isChecked())
print(c.text)
```

```
False
True
라떼
```

```python
a = CheckBox("A")
b = CheckBox("B")
a.setChecked(True)
print(a.isChecked(), b.isChecked())
```

```
True False
```

- 출력은 글자 하나까지 같아야 합니다. `False`/`True` 는 불(bool) 값이어야 하며 `0`/`1` 이 출력되면 오답입니다.

## s14_p17 (정규표현식 · 빈칸 채우기 · 대문자 약어 뽑기 · 4점)

파일: `s14_p17.py`

한 줄을 입력받아, 영문 대문자가 2개 이상 이어진 덩어리(예: `NASA`, `AI`)를 모두 찾아 리스트로 출력하는
프로그램입니다. 빈칸(`____`) 1곳을 채워 프로그램을 완성하세요.

```python
import re

text = input()
words = re.findall(____, text)   # 영문 대문자가 2개 이상 이어진 덩어리
print(words)
```

- 빈칸에는 정규식 패턴 문자열이 들어갑니다.
- 대문자가 1개뿐인 곳(`Google` 의 `G`)은 뽑지 않습니다. 소문자, 숫자, 밑줄은 덩어리에 포함되지 않습니다.
- 대문자가 몇 개 이어지든 한 덩어리로 뽑습니다. `ABCDEF` 는 `['ABCDEF']` 입니다.
- 매치되는 것이 없으면 `[]` 를 출력합니다.
- **빈칸만** 채웁니다. 다른 줄을 고치거나 줄을 추가하면 오답 처리됩니다.

## 입출력 예

| 입력 | 출력 |
|---|---|
| `NASA is working on AI projects with IBM and Google.` | `['NASA', 'AI', 'IBM']` |
| `I am a Robot` | `[]` |
| `USA2024 and KOREA_ROK` | `['USA', 'KOREA', 'ROK']` |

## s21_p03 (파이썬 활용 심화(os·pathlib·JSON) · 출력 · 폴더 안의 항목 확인하기 · 4점)

파일: `s21_p03.py`

현재 폴더에 `sample_folder` 라는 폴더가 있습니다. 이름 하나를 입력받아, `os` 모듈로 `sample_folder` 안의 파일과 폴더 목록을 구한 뒤 아래 두 줄을 출력하는 프로그램을 작성하세요.

- 첫째 줄: `항목 수: N` (`N` 은 `sample_folder` 바로 안에 있는 파일과 폴더의 개수)
- 둘째 줄: 입력받은 이름이 목록에 있으면 `이름 있음`, 없으면 `이름 없음`
- 목록에는 `sample_folder` 바로 안에 있는 파일과 폴더의 이름만 들어 있습니다. 하위 폴더 안에 든 파일은 세지 않습니다.
- 목록의 순서는 운영 체제에 따라 달라질 수 있으므로 목록 자체는 출력하지 않습니다.
- 콜론(`:`) 뒤와 이름 뒤에 공백이 한 칸 있습니다.

## 입출력 예

`sample_folder` 안에 파일 `memo.txt`, `data.csv` 와 폴더 `images` 가 있고, `images` 폴더 안에 `cat.png` 가 있을 때

| 입력 | 출력 |
|---|---|
| `memo.txt` | `항목 수: 3`⏎`memo.txt 있음` |
| `report.txt` | `항목 수: 3`⏎`report.txt 없음` |
| `images` | `항목 수: 3`⏎`images 있음` |

첫 번째 예의 출력

```
항목 수: 3
memo.txt 있음
```

- 출력은 글자 하나까지 같아야 합니다(띄어쓰기 포함).

