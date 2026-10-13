# 3회차 미니 모의고사

> 프로그램(`python study.py`)에서 풀면 이 폴더의 `quiz.py` 와 `.py` 파일에 답이 자동으로 저장됩니다.

문항 18개(보강할 단원 16개) · 평균 레벨 1.8 · 단원: s05 3, s13 3, s08 2, s02 1, s04 1, s07 1, s09 1, s10 1, s12 1, s15 1, s16 1, s19 1, s20 1

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

## s05_Q11 (반복문 · 출력 예측 · 3점)

다음 코드의 출력 결과를 그대로 적으세요.

```python
for i in range(1, 10):
    if i == 7:
        break
    elif i % 3 == 0:
        continue
    print(i)
```

## s05_Q13 (반복문 · 출력 예측 · 3점)

다음 코드의 출력 결과를 그대로 적으세요.
(주간 요약본 예제처럼 f-string 을 썼습니다. `f"..."` 안의 `{i}` 자리에는 변수 `i` 의 값이 들어갑니다.)

```python
for i in range(2):
    for j in range(2):
        print(f"i={i}, j={j}")
```

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

## s10_Q21 (클래스(2) · 출력 예측 · 3점)

다음 코드의 출력 결과를 그대로 적으세요. (`pass` 는 아무 일도 하지 않는 자리 채움 문장입니다)

```python
class Staff:
    def __init__(self, name):
        self.name = name

    def pay(self):
        return 100


class Driver(Staff):
    def pay(self):
        return 150


class Intern(Staff):
    pass


team = [Driver("Kim"), Intern("Lee"), Staff("Park")]
total = 0
for member in team:
    print(member.name, member.pay())
    total = total + member.pay()
print(total)
```

## s12_Q5 (파일 처리 · 객관식 · 2점)

현재 폴더에 `data.txt` 파일이 **없을 때**, 실행하면 오류가 발생하는 것은?

1. `f = open("data.txt", "w")`
2. `f = open("data.txt", "a")`
3. `f = open("data.txt")`
4. `f = open("data.txt", "w", encoding="utf-8")`

## s13_Q3 (예외 처리·문자열·람다·map · 객관식 · 2점)

`ValueError` 와 `ZeroDivisionError` 를 **하나의** `except` 절에서 **둘 다** 잡으려고 합니다. 올바른 코드는?

1. `except ValueError and ZeroDivisionError:`
2. `except (ValueError, ZeroDivisionError):`
3. `except [ValueError, ZeroDivisionError]:`
4. `except ValueError or ZeroDivisionError:`

## s13_Q11 (예외 처리·문자열·람다·map · 출력 예측 · 3점)

다음 코드의 출력 결과를 그대로 적으세요.

```python
def divide(a, b):
    try:
        print("계산 시작")
        result = a / b
        print("결과:", result)
    except ZeroDivisionError:
        print("0으로 나눌 수 없습니다")
    finally:
        print("계산 종료")

divide(10, 4)
divide(3, 0)
```

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

## s19_Q36 (statsmodels·scikit-learn·SciPy · 객관식 · 2점)

강의에 나온 이름과 그 설명의 짝으로 옳지 **않은** 것은?

1. `OLS` 는 Ordinary Least Squares 의 줄임말이고, 오차의 제곱을 최소화하는 기울기와 절편을 추정하는 방식이다.
2. `SVC` 는 서포트 벡터 분류(Support Vector Classification)이고, 최대 마진을 가진 최적의 선(평면)을 찾아 데이터를 분류한다.
3. `metrics` 는 성능 지표를 모아 둔 모듈이고, `accuracy_score()` 가 정답률을 계산한다.
4. `fit()` 은 시험 데이터에 대해 분류를 수행하고, `predict()` 는 훈련 데이터에 따라 모델을 피팅한다.

## s20_Q4 (Seaborn·OpenCV · 객관식 · 2점)

OpenCV 에서 이미지의 크기를 조정하는 함수는?

1. `cv2.resize()`
2. `cv2.rescale()`
3. `cv2.scale()`
4. `cv2.transform()`

## s02_p03 (프로그래밍 기초 · 반환값 · 문자열로 적힌 두 수의 합 · 4점)

파일: `s02_p03.py`

정수가 **문자열**로 적힌 `a`, `b` 가 주어집니다(예: `"12"`, `"30"`).
두 수를 숫자로 더한 값을 **정수로 반환(return)** 하는 `solution` 함수를 완성하세요.

- 함수 이름과 매개변수는 바꾸지 않습니다. `def` 줄과 `return answer` 줄 사이에, `answer` 줄과 같은 칸(공백 4칸)에 맞춰 코드를 작성합니다.
- 구한 답을 `answer` 에 저장하면 `return answer` 줄이 그 값을 돌려줍니다. `print` 로 출력만 하면 오답입니다.
- 반환값의 자료형은 정수(int)여야 합니다. `"42"` 같은 문자열을 반환하면 오답입니다.

## 제한 사항
- `a`, `b` 는 -1000 이상 1000 이하의 정수를 문자열로 적은 것입니다.

## 입출력 예

| a | b | 반환값 |
|---|---|---|
| `"12"` | `"30"` | `42` |
| `"7"` | `"8"` | `15` |
| `"-5"` | `"5"` | `0` |

## s04_p04 (리스트와 딕셔너리 · 반환값 · 처음과 끝의 합 · 4점)

파일: `s04_p04.py`

정수가 담긴 리스트 `nums` 가 주어질 때, 첫 번째 요소와 마지막 요소의 합을 **반환(return)** 하는 `solution` 함수를 완성하세요.

- 함수 이름과 매개변수는 바꾸지 않습니다.
- `print` 로 출력하는 것이 아니라 `return` 으로 돌려줘야 합니다.
- 요소가 하나뿐이면 그 요소가 첫 번째이자 마지막이므로 두 번 더합니다.

## 제한 사항
- `nums` 의 길이는 1 이상 100 이하
- `nums` 의 요소는 -1000 이상 1000 이하의 정수

## 입출력 예

| nums | 반환값 |
|---|---|
| `[1, 2, 3]` | `4` |
| `[10, 20, 30, 40, 50]` | `60` |
| `[7]` | `14` |

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

## s09_p05 (클래스(1) · 반환값 · 장바구니에 여러 개 담기 · 6점)

파일: `s09_p05.py`

장바구니를 나타내는 `Cart` 클래스의 메서드 두 개를 완성하세요. `__init__` 과 `solution` 함수는 이미 작성되어 있으며 고치지 않습니다.

| 메서드 | 하는 일 |
|---|---|
| `put(item)` | `item` 을 리스트 `self.items` 의 맨 뒤에 추가 |
| `put_many(item, count)` | `item` 을 `count` 번 담기. **`put` 메서드를 `count` 번 호출**해서 구현 |

`solution(names, counts)` 는 장바구니를 하나 만들고, `names[i]` 를 `counts[i]` 개씩 차례로 담은 뒤 장바구니의 `items` 리스트를 반환합니다.

- 시작 코드의 `pass` 는 아무 일도 하지 않는 자리 채움 문장이므로, 지우고 그 자리에 코드를 작성하세요.

## 제한 사항
- `names` 와 `counts` 의 길이는 같고, 0 이상 10 이하
- `counts` 의 원소는 0 이상 5 이하의 정수

## 입출력 예

| names | counts | 반환값 |
|---|---|---|
| `["apple", "milk"]` | `[2, 1]` | `['apple', 'apple', 'milk']` |
| `["tea"]` | `[3]` | `['tea', 'tea', 'tea']` |
| `["a", "b"]` | `[0, 2]` | `['b', 'b']` |

## s15_p15 (고급 함수 · 반환값 · 짝수의 제곱 이터레이터 · 6점)

파일: `s15_p15.py`

정수 `n` 이 주어질 때, 0 부터 `n` 까지의 정수 가운데 짝수만 골라 그 제곱을 작은 수부터 하나씩 돌려주는 **이터레이터**를 반환(return)하는 `solution` 함수를 완성하세요.

예를 들어 `n` 이 6 이면 0, 2, 4, 6 의 제곱인 0, 4, 16, 36 을 차례로 돌려줍니다.

- 반환값은 리스트가 아니라 `next()` 에 바로 넣을 수 있는 이터레이터여야 합니다. `iter()` 로 바꾼 것, 제너레이터 표현식, `yield` 를 쓴 제너레이터 가운데 어느 것으로 만들어도 됩니다.
- `n` 도 범위에 들어갑니다. 0 은 짝수입니다.
- 채점은 `next(solution(...))`, `sum(solution(...))`, `list(solution(...))` 으로 확인합니다.

## 제한 사항
- 0 ≤ n ≤ 1000

## 입출력 예

| 호출 | 결과 |
|---|---|
| `next(solution(9))` | `0` |
| `sum(solution(4))` | `20` |
| `list(solution(6))` | `[0, 4, 16, 36]` |
| `list(solution(0))` | `[0]` |

## s16_p15 (알고리즘(1) · 출력 · 비어 있으면 -1 을 돌려주는 큐 · 6점)

파일: `s16_p15.py`

리스트를 이용해 큐를 구현한 `Queue` 클래스를 정의하세요.

| 구분 | 이름 | 내용 |
|---|---|---|
| 생성자 | `__init__()` | 빈 리스트를 인스턴스 변수 `queue` 로 만듭니다 |
| 메서드 | `enqueue(x)` | `x` 를 큐의 맨 뒤에 넣습니다 |
| 메서드 | `dequeue()` | 큐의 맨 앞 값을 제거하고 반환합니다. 큐가 비어 있으면 정수 `-1` 을 반환합니다 |
| 메서드 | `front()` | 큐의 맨 앞 값을 제거하지 않고 반환합니다. 큐가 비어 있으면 정수 `-1` 을 반환합니다 |
| 메서드 | `is_empty()` | 큐가 비어 있으면 `True`, 아니면 `False` 를 반환합니다 |

- 클래스만 정의하면 됩니다. 채점할 때는 아래와 같은 테스트 코드가 객체를 만들어 메서드를 호출합니다.
- 메서드는 값을 출력하지 않고 반환합니다.
- 리스트의 앞이 큐의 앞입니다. 테스트 코드가 `queue` 를 그대로 출력하므로 인스턴스 변수 이름을 바꾸지 않습니다.

## 테스트 코드와 출력 예

은행에 온 순서대로 고객을 넣고, 가장 먼저 온 고객부터 업무를 처리하는 코드입니다.

```python
bank = Queue()
bank.enqueue("김철수")
bank.enqueue("이영희")
bank.enqueue("박민수")
print("현재 대기열:", bank.queue)
print("업무 처리 중인 고객:", bank.dequeue())
print("남은 대기 고객:", bank.queue)
```

```
현재 대기열: ['김철수', '이영희', '박민수']
업무 처리 중인 고객: 김철수
남은 대기 고객: ['이영희', '박민수']
```

```python
q = Queue()
print(q.dequeue())
print(q.front())
print(q.is_empty())
```

```
-1
-1
True
```

