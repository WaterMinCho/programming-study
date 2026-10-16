# 16차시 퀴즈: 알고리즘(1)

> 코드를 실행하지 말고 눈으로 풀어 보세요. 답은 `submissions/<내 ID>/s16/quiz.py` 에 적습니다.

## Q1 (객관식 · 2점)

알고리즘과 자료구조에 대한 설명으로 옳지 **않은** 것은?

1. 알고리즘은 문제를 해결하기 위한 명확한 절차나 방법이다.
2. 자료구조는 데이터를 저장하고 관리하는 방법이다.
3. 상황에 맞는 자료구조를 고르면 프로그램의 속도와 효율을 높일 수 있다.
4. 스택과 큐는 데이터를 넣은 순서와 꺼내는 순서가 언제나 같다.

## Q2 (객관식 · 2점)

스택(Stack)에 대한 설명으로 옳지 **않은** 것은?

1. 데이터의 삽입과 삭제가 한쪽 끝(top)에서만 일어난다.
2. 가장 나중에 넣은 데이터가 가장 먼저 나오는 후입선출(LIFO) 구조이다.
3. 먼저 들어온 데이터가 먼저 나가므로 줄 서기에 비유할 수 있다.
4. 함수 호출 관리나 웹 브라우저의 뒤로 가기 기능에 활용된다.

## Q3 (객관식 · 2점)

다음 중 강의에서 **큐(Queue)** 의 활용 사례로 소개한 것은?

1. 문자열 회문 검사
2. 웹 브라우저의 뒤로 가기
3. 괄호 짝 검사
4. 운영체제의 작업 대기열(프로세스 관리)

## Q4 (객관식 · 2점)

리스트 `queue` 로 큐를 구현했을 때, **dequeue**(가장 먼저 넣은 데이터를 제거)에 해당하는 코드는?

1. `queue.pop()`
2. `queue.pop(0)`
3. `queue.append(0)`
4. `queue.remove(0)`

## Q5 (객관식 · 2점)

덱(Deque)에 대한 설명으로 옳지 **않은** 것은?

1. 양쪽 끝에서 데이터의 삽입과 삭제가 모두 가능하다.
2. Double Ended Queue 의 줄임말로, 스택과 큐를 합친 형태의 자료구조이다.
3. 파이썬에서는 `collections` 모듈의 `deque` 클래스를 사용한다.
4. `appendleft()` 는 덱의 마지막에 데이터를 넣는 메서드이다.

## Q6 (출력 예측 · 3점)

다음 코드의 출력 결과를 그대로 적으세요.

```python
stack = []
stack.append(10)
stack.append(20)
stack.append(30)
top = stack.pop()
stack.append(40)
print(top)
print(stack)
print(stack.pop(), stack.pop())
print(stack)
```

## Q7 (출력 예측 · 3점)

다음 코드의 출력 결과를 그대로 적으세요.

```python
queue = []
queue.append("A")
queue.append("B")
first = queue.pop(0)
queue.append("C")
queue.append("D")
print(first)
print(queue)
print(queue.pop(0))
print(queue)
```

## Q8 (객관식 · 2점)

다음 코드를 실행한 결과로 옳은 것은?

```python
queue = [1]
queue.pop(0)
print(queue.pop(0))
```

1. `None` 이 출력된다.
2. `1` 이 출력된다.
3. `[]` 이 출력된다.
4. 오류가 발생한다.

## Q9 (출력 예측 · 3점)

다음 코드의 출력 결과를 그대로 적으세요.

```python
class Stack:
    def __init__(self):
        self.stack = []

    def push(self, data):
        self.stack.append(data)

    def pop(self):
        if not self.is_empty():
            return self.stack.pop()
        return

    def is_empty(self):
        if len(self.stack) == 0:
            return True
        return False

    def peak(self):
        if not self.is_empty():
            return self.stack[-1]
        return

s = Stack()
print(s.pop())
s.push(5)
s.push(7)
print(s.peak())
s.pop()
s.push(9)
print(s.peak(), s.is_empty())
print(s.stack)
```

## Q10 (출력 예측 · 3점)

다음 코드의 출력 결과를 그대로 적으세요.

```python
from collections import deque

dq = deque()
dq.append(1)
dq.append(2)
dq.appendleft(3)
print(dq)
dq.pop()
dq.appendleft(4)
print(dq)
print(dq.popleft(), dq.popleft())
print(dq)
```

## Q11 (객관식 · 2점)

다음 두 세트에 대해 결과가 `{1, 2}` 가 되는 식은?

```python
a = {1, 2, 3, 3}
b = {3, 4}
```

1. `a & b`
2. `a | b`
3. `a - b`
4. `b - a`

## Q12 (객관식 · 2점)

다음 코드를 실행했을 때 출력되는 것은?

```python
numbers = {5, 1, 5, 3, 1}
numbers.add(3)
numbers.remove(5)
print(len(numbers))
```

1. `2`
2. `3`
3. `4`
4. `6`

## Q13 (단답 · 3점)

큐(Queue)에 데이터를 삽입하는 연산의 이름을 영어로 적으세요. 스택의 push 에 해당하는 이름을 묻는 문제이고, 리스트 메서드 `append` 는 답이 아닙니다.

## Q14 (단답 · 3점)

`deque` 클래스가 들어 있는 파이썬 내장 모듈의 이름을 적으세요. (`from 모듈 import deque` 에서 `모듈` 자리에 들어가는 이름)

## Q15 (출력 예측 · 3점)

다음 코드의 출력 결과를 그대로 적으세요.

```python
class Queue:
    def __init__(self):
        self.queue = []

    def enqueue(self, data):
        self.queue.append(data)

    def dequeue(self):
        if not self.is_empty():
            return self.queue.pop(0)
        return

    def is_empty(self):
        if len(self.queue) == 0:
            return True
        return False

    def status_queue(self):
        return self.queue


q = Queue()
q.dequeue()
q.enqueue("a")
q.enqueue("b")
view = q.status_queue()
q.enqueue("c")
print(q.dequeue(), view)
view.append("z")
print(q.dequeue(), q.dequeue(), q.dequeue(), q.dequeue())
print(view, q.is_empty())
```

## Q16 (출력 예측 · 3점)

다음 코드의 출력 결과를 그대로 적으세요. `Line` 은 `Stack` 을 상속하면서 `pop` 메서드만 다시 정의한 클래스입니다.

```python
class Stack:
    def __init__(self):
        self.stack = []

    def push(self, data):
        self.stack.append(data)

    def pop(self):
        if not self.is_empty():
            return self.stack.pop()
        return

    def is_empty(self):
        if len(self.stack) == 0:
            return True
        return False

    def peak(self):
        if not self.is_empty():
            return self.stack[-1]
        return


class Line(Stack):
    def pop(self):
        if not self.is_empty():
            return self.stack.pop(0)
        return


s = Stack()
q = Line()
for n in [3, 6, 9]:
    s.push(n)
    q.push(n)
print(s.pop(), q.pop())
print(s.peak(), q.peak())
q.pop()
q.pop()
print(q.pop(), q.is_empty())
print(s.stack, q.stack)
```

## Q17 (출력 예측 · 3점)

다음 코드의 출력 결과를 그대로 적으세요.

```python
data = [3, 1, 4]
out = []
try:
    while True:
        out.append(data.pop(0))
        out.append(data.pop())
except IndexError:
    print("stop", out)
finally:
    print(data)
print(len(out))
```

## Q18 (출력 예측 · 3점)

다음 코드의 출력 결과를 그대로 적으세요.

```python
from collections import deque

dq = deque()
for ch in "abc":
    dq.appendleft(ch)
print(dq)
dq.appendleft(dq.pop())
print(dq)
print(dq.pop(), dq.popleft(), dq.pop())
print(dq, len(dq))
```

## Q19 (객관식 · 2점)

리스트 `data = [1, 2, 3, 4, 5]` 를 왼쪽으로 2만큼 회전하면 `[3, 4, 5, 1, 2]` 가 됩니다.
처음 상태의 `data` 에 각 보기를 따로 실행했을 때 `data` 가 `[3, 4, 5, 1, 2]` 가 되는 것을 **모두** 고르세요.

1. `data.append(data.pop(0))` 을 2번 실행
2. `data.insert(0, data.pop())` 을 2번 실행
3. `data.insert(0, data.pop())` 을 3번 실행
4. `data.append(data.pop())` 을 2번 실행
5. `data = data[2:] + data[:2]` 를 1번 실행

## Q20 (객관식 · 2점)

파이썬 리스트를 스택으로 사용할 때, 가장 나중에 넣은 요소를 제거하는 메서드는?

1. `pop()`
2. `remove()`
3. `del`
4. `discard()`

## Q21 (객관식 · 2점)

큐(Queue) 자료구조의 주요 특징은?

1. LIFO (Last In First Out)
2. FIFO (First In First Out)
3. 정렬된 데이터 관리
4. 랜덤 접근 가능

## Q22 (출력 예측 · 3점)

다음 코드의 출력 결과를 그대로 적으세요.

```python
class Stack:
    def __init__(self):
        self.stack = ['두산', '로키', '부트']

    def push(self, data):
        self.stack.append(data)

    def pop(self):
        if not self.is_empty():
            return self.stack.pop()
        return

    def is_empty(self):
        return len(self.stack) == 0

    def peak(self):
        if not self.is_empty():
            return self.stack[-1]
        return

    def status_stack(self):
        return self.stack


s = Stack()
s.push("캠프")
print(s.status_stack())
print(s.pop())
print(s.status_stack())
print(s.peak(), s.is_empty())
```

## Q23 (출력 예측 · 3점)

다음 코드의 출력 결과를 그대로 적으세요.

```python
class Stack:
    def __init__(self):
        self.stack = []

    def push(self, x):
        self.stack.append(x)

    def pop(self):
        if self.is_empty():
            return -1
        return self.stack.pop()

    def top(self):
        if self.is_empty():
            return -1
        return self.stack[-1]

    def is_empty(self):
        return len(self.stack) == 0


s = Stack()
print(s.top(), s.is_empty())
s.push(4)
s.push(8)
print(s.top(), s.pop(), s.top())
print(s.pop(), s.pop())
print(s.stack, s.is_empty())
```

## Q24 (출력 예측 · 3점)

후위 표기법은 연산자를 피연산자 뒤에 적는 표기법입니다. `3 4 +` 는 `3 + 4` 를 나타냅니다.
후위 표기법 수식을 스택으로 계산하는 다음 코드의 출력 결과를 그대로 적으세요.

```python
expr = "7 2 3 * - 8 4 / +"
stack = []
for t in expr.split():
    if t == "+" or t == "-" or t == "*" or t == "/":
        b = stack.pop()
        a = stack.pop()
        if t == "+":
            stack.append(a + b)
        elif t == "-":
            stack.append(a - b)
        elif t == "*":
            stack.append(a * b)
        else:
            stack.append(a / b)
        print(t, stack)
    else:
        stack.append(int(t))
```

## Q25 (객관식 · 2점)

`collections` 의 `deque` 를 쓰지 않고 리스트 `data` 로 덱을 구현하려고 합니다. 덱의 연산과 리스트 코드의 연결이 옳지 **않은** 것은?

1. 앞에 넣기 `push_front(x)` 는 `data.insert(0, x)`
2. 뒤에 넣기 `push_back(x)` 는 `data.append(x)`
3. 앞에서 꺼내기 `pop_front()` 는 `data.popleft()`
4. 뒤에서 꺼내기 `pop_back()` 은 `data.pop()`

## Q26 (객관식 · 2점)

스택(Stack) 자료구조의 주요 특징은?

1. FIFO (First In First Out)
2. LIFO (Last In First Out)
3. 정렬된 데이터 관리
4. 랜덤 접근 가능

## Q27 (객관식 · 2점)

덱(Deque)의 주요 특징은?

1. 한쪽에서만 삽입과 삭제가 가능하다.
2. 양쪽 끝에서 삽입과 삭제가 가능하다.
3. 데이터를 자동으로 정렬한다.
4. LIFO만 지원한다.
