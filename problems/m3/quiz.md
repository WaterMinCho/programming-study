# 모의고사 3회 (1~21차시) 퀴즈

> 코드를 실행하지 말고 눈으로 풀어 보세요. 답은 `submissions/<내 ID>/m3/quiz.py` 에 적습니다.
> 출력 예측 문항은 여러 줄이면 `"""` 로 감싸서 줄을 나눠 적고, 띄어쓰기와 따옴표까지 정확히 적습니다.
> pandas, NumPy, scikit-learn, OpenCV, openpyxl 코드가 나오는 문항은 그 패키지가 설치되어 있다고 가정합니다.

## Q1 (객관식 · 2점)

다음 코드를 실행했을 때 출력되는 것은?

```python
menu = {"김밥": 3500, "라면": 4000}
menu["우동"] = 5000
menu["김밥"] += 500
names = []
for name in menu.keys():
    names.append(name)
first = menu["김밥"]
del menu["라면"]
t = (names[-1], len(menu), first)
print(t, "라면" in menu, len(names))
```

1. `('우동', 2, 3500) False 3`
2. `['우동', 2, 4000] False 3`
3. `('우동', 2, 4000) False 3`
4. `('우동', 2, 4000) False 2`

## Q2 (출력 예측 · 3점)

다음 코드의 출력 결과를 그대로 적으세요. (여러 줄이면 `"""` 로 감싸서 줄을 나눠 적습니다)

```python
total = 10

def add(x, step=2):
    total = x + step
    return total

def bump(x):
    global total
    total += x

print(add(3), total)
print(bump(5), total)
print(add(total, 0) + add(1))
```

## Q3 (출력 예측 · 3점)

다음 코드의 출력 결과를 그대로 적으세요. (여러 줄이면 `"""` 로 감싸서 줄을 나눠 적습니다)

```python
class Ticket:
    count = 0

    def __init__(self, seat):
        self.seat = seat
        Ticket.count += 1
        self.number = Ticket.count

    def move(self, seat):
        old = self.seat
        self.seat = seat
        return old


a = Ticket("A1")
b = Ticket("B2")
c = b
print(c.move("C3"), b.seat)
b.count = 10
print(a.count, b.count, Ticket.count)
print(a.number, c.number, c.count)
```

## Q4 (객관식 · 2점)

다음 코드를 실행했을 때 출력되는 것은?

```python
class Menu:
    tax = 10

    def __init__(self, name, price):
        self.name = name
        self.price = price

    def total(self):
        return self.price + self.price * self.tax // 100

    def show(self):
        print(self.name, self.total())


class SetMenu(Menu):
    tax = 20

    def __init__(self, name, price, drink):
        super().__init__(name + "세트", price)
        self.drink = drink

    def total(self):
        return super().total() + self.drink


m = SetMenu("버거", 5000, 1500)
m.show()
```

1. `버거세트 7000`
2. `버거세트 7500`
3. `버거 7500`
4. `버거세트 6000`

## Q5 (객관식 · 2점)

다음 코드를 실행했을 때의 결과로 옳은 것은?

```python
class Animal:
    def __init__(self, name):
        self.name = name

    def speak(self):
        return "..."


class Dog(Animal):
    def speak(self):
        return "멍멍"

    def fetch(self):
        return self.name + " 물어 옴"


pets = [Dog("초코"), Animal("나비")]
for p in pets:
    print(p.speak())      # (가)
    print(p.fetch())      # (나)
```

1. `멍멍`, `초코 물어 옴`, `...`, `나비 물어 옴` 네 줄이 모두 출력된다.
2. `Dog` 에는 `__init__` 이 없으므로 `Dog("초코")` 에서 오류가 발생한다.
3. `멍멍`, `초코 물어 옴`, `...` 이 출력된 뒤 (나)에서 오류가 발생한다.
4. `멍멍` 이 출력된 뒤, `Dog` 객체에는 `name` 이 없어 (나)에서 오류가 발생한다.

## Q6 (출력 예측 · 3점)

다음 코드의 출력 결과를 그대로 적으세요. (`note.txt` 는 처음에 없습니다)

```python
with open("note.txt", "w", encoding="utf-8") as f:
    f.write("a,1\n")
    f.write("b,2\nc,3\n")
with open("note.txt", "a", encoding="utf-8") as f:
    f.write("d,4")
total = 0
with open("note.txt", "r", encoding="utf-8") as f:
    first = f.readline()
    lines = f.readlines()
for line in lines:
    parts = line.strip().split(",")
    total += int(parts[1])
    print(parts[0], end=" ")
print(total)
print(len(first), len(lines), first.strip())
```

## Q7 (객관식 · 2점)

다음 코드를 실행했을 때 출력되는 것은?

```python
def to_float(text):
    try:
        return float(text)
    except ValueError:
        return 0
    finally:
        print("끝", end=" ")

print(to_float("2.5"), to_float(""))
```

1. `2.5 끝 0 끝`
2. `2.5 0`
3. `끝 2.5 끝 0`
4. `끝 끝 2.5 0`

## Q8 (출력 예측 · 3점)

다음 코드의 출력 결과를 그대로 적으세요. (여러 줄이면 `"""` 로 감싸서 줄을 나눠 적습니다)

```python
def to_count(text):
    try:
        count = int(text)
    except ValueError:
        print("숫자 아님")
        return 0
    if count > 99:
        raise ValueError("99 초과")
    print("수량", count)
    return count * 2

for text in ["20", "3.5", "120", "8"]:
    try:
        print(to_count(text))
    except ValueError as e:
        print("오류:", e)
print("끝")
```

## Q9 (출력 예측 · 3점)

다음 코드의 출력 결과를 그대로 적으세요. (여러 줄이면 `"""` 로 감싸서 줄을 나눠 적습니다)

```python
import re

data = """python one
you need python
Python two
python 3"""

p = re.compile(r"^python\s\w+")
q = re.compile(r"^python\s\w+", re.M)
print(p.findall(data))
print(q.findall(data))
print(p.match(data).span(), q.search("go python go"))
```

## Q10 (객관식 · 2점)

다음 코드를 실행했을 때 출력되는 줄을 위에서부터 순서대로 적은 것은?

```python
def gen():
    print("시작")
    yield 1
    print("중간")
    yield 2
    print("끝")

g = gen()
print("준비")
for x in g:
    print(x)
```

1. `준비`, `시작`, `1`, `중간`, `2`, `끝`
2. `시작`, `준비`, `1`, `중간`, `2`, `끝`
3. `준비`, `시작`, `1`, `중간`, `2`
4. `시작`, `중간`, `끝`, `준비`, `1`, `2`

## Q11 (단답 · 3점)

다음 코드를 실행했을 때 출력되는 값을 적으세요.

```python
stack = []
queue = []
for n in [3, 1, 4, 1, 5]:
    if n % 2 == 1:
        stack.append(n)
    else:
        queue.append(n)
    if len(stack) == 3:
        queue.append(stack.pop())
print(stack.pop() * 10 + queue.pop(0))
```

## Q12 (단답 · 3점)

그래프가 아래 딕셔너리로 주어집니다. 키는 노드이고 값은 그 노드와 이어진 노드의 리스트입니다. 노드 `1` 에서 출발해 너비 우선 탐색(BFS)으로 모든 노드를 방문할 때 **6번째**로 방문하는 노드를 숫자만 적으세요. 시작 노드가 1번째이고, 한 노드에 이어진 노드가 여럿이면 리스트의 앞에 적힌 노드부터 큐에 넣습니다.

```python
graph = {
    1: [4, 2],
    2: [1, 5, 3],
    3: [2, 6],
    4: [1, 6],
    5: [2],
    6: [4, 3, 7],
    7: [6],
}
```

## Q13 (객관식 · 2점)

다음 코드에 대한 설명으로 옳은 것은?

```python
import pandas as pd

df = pd.DataFrame({
    "name": ["kim", "lee", "park", "choi"],
    "age": [25, 32, 41, 30],
    "pay": [300, 280, 500, 450],
})
picked = df[(df["age"] >= 30) & (df["pay"] > 280)]
print(len(picked), picked["pay"].sum())
```

1. `picked` 에는 lee, park, choi 세 사람의 행이 들어 있다.
2. 마지막 줄은 `2 950` 을 출력한다.
3. `print(picked)` 로 출력하면 맨 왼쪽의 인덱스가 0, 1 로 새로 매겨져 있다.
4. 조건을 `df[df["age"] >= 30 and df["pay"] > 280]` 으로 써도 같은 결과가 나온다.

## Q14 (객관식 · 2점)

다음 코드를 실행했을 때 출력되는 것은?

```python
import numpy as np

a = [1, 2, 3]
b = np.array([1, 2, 3])
print(a * 2, b * 2, (b[b > 1] + 10).sum())
```

1. `[2, 4, 6] [2 4 6] 25`
2. `[1, 2, 3, 1, 2, 3] [2, 4, 6] 25`
3. `[1, 2, 3, 1, 2, 3] [2 4 6] 36`
4. `[1, 2, 3, 1, 2, 3] [2 4 6] 25`

## Q15 (객관식 · 2점)

훈련용 데이터(`train_data`, `train_label`)로 모델을 학습시키고, 시험용 데이터(`test_data`)의 결과를 예측한 뒤 정답률을 출력하는 코드입니다. (가), (나)에 들어갈 메서드와 마지막 줄의 출력을 옳게 짝지은 것은?

```python
from sklearn import svm, metrics

clf = svm.SVC()
clf.(가)(train_data, train_label)
pre = clf.(나)(test_data)
print(pre)                                       # [0 1 1 0] 이 출력됨
print(metrics.accuracy_score([0, 1, 0, 0], pre))
```

1. (가) `fit` (나) `predict` 출력 `0.75`
2. (가) `fit` (나) `predict` 출력 `75`
3. (가) `predict` (나) `fit` 출력 `0.75`
4. (가) `train` (나) `test` 출력 `3`

## Q16 (객관식 · 2점)

컬러 이미지 파일을 읽어 흑백(그레이스케일)으로 바꾼 뒤 창에 보여 주고, 키를 누를 때까지 기다렸다가 창을 닫는 프로그램입니다. (가), (나), (다)에 들어갈 것을 순서대로 바르게 적은 것은?

```python
import cv2

image = cv2.(가)("color.jpg")
gray = cv2.cvtColor(image, (나))
cv2.imshow("Gray", gray)
cv2.(다)(0)
cv2.destroyAllWindows()
```

1. (가) `imshow` (나) `cv2.COLOR_BGR2GRAY` (다) `waitKey`
2. (가) `imread` (나) `cv2.COLOR_BGR2GRAY` (다) `waitKey`
3. (가) `imread` (나) `cv2.COLOR_GRAY` (다) `waitKey`
4. (가) `imread` (나) `cv2.COLOR_BGR2GRAY` (다) `destroyAllWindows`

## Q17 (객관식 · 2점)

`score.xlsx` 의 첫 번째 시트 B1 셀에 숫자 `80` 이 들어 있습니다. 이 파일을 불러와 B2 셀에 B1 값보다 10 큰 값을 넣고 같은 파일에 저장하려고 합니다. (가), (나), (다)에 들어갈 것을 순서대로 바르게 적은 것은?

```python
from openpyxl import (가)

wb = (가)("score.xlsx")
sheet = wb.(나)
sheet["B2"] = sheet["B1"].(다) + 10
wb.save("score.xlsx")
```

1. (가) `Workbook` (나) `active` (다) `value`
2. (가) `load_workbook` (나) `active()` (다) `value`
3. (가) `load_workbook` (나) `active` (다) `value`
4. (가) `read_excel` (나) `sheet` (다) `text`

## Q18 (출력 예측 · 3점)

다음 코드의 출력 결과를 그대로 적으세요. 따옴표의 종류와 들여쓰기 칸 수까지 같아야 합니다.

```python
import json

text = '[{"name": "kim", "score": [80, 95]}, {"name": "lee", "score": [70]}]'
rows = json.loads(text)
total = {}
for row in rows:
    total[row["name"]] = sum(row["score"])
print(len(rows), rows[1]["score"])
print(total)
print(json.dumps(total))
print(json.dumps(total, indent=4))
```
