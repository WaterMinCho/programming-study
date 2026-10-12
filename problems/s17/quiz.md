# 17차시 퀴즈: 알고리즘(2)

> 코드를 실행하지 말고 눈으로 풀어 보세요. 답은 `submissions/<내 ID>/s17/quiz.py` 에 적습니다.

## Q1 (객관식 · 2점)

그래프의 용어에 대한 설명으로 옳지 **않은** 것은?

1. 그래프는 관계를 표현하는 구조이며, 트리(Tree) 구조를 이해하는 데 필요하다.
2. 그래프는 노드(Node)와 엣지(Edge)로 구성되고, 노드는 정점(Vertex)이라고도 한다.
3. 두 노드 사이에 엣지가 있으면 두 노드는 인접해 있다고 한다.
4. 차수(degree)는 한 노드에서 다른 노드까지 가는 길에 놓인 노드들의 순서이다.

## Q2 (객관식 · 2점)

도시를 노드로, 도로를 엣지로 두고 도로마다 이동하는 데 걸리는 시간을 적어 둔 그래프가 있습니다.
이처럼 엣지에 비용이나 시간 같은 값을 붙인 그래프를 무엇이라고 하는가?

1. 무방향 그래프(undirected graph)
2. 방향 그래프(directed graph)
3. 가중 그래프(weighted graph)
4. 인접 그래프(adjacent graph)

## Q3 (객관식 · 2점)

DFS(깊이 우선 탐색)를 사용해 해결하기에 가장 적합한 문제는?

1. 두 노드 사이의 최단 경로 탐색
2. 연결 요소의 탐색(서로 이어진 노드를 빠짐없이 방문하기)
3. 동적 계획법 문제
4. 해시 탐색

## Q4 (객관식 · 2점)

BFS(너비 우선 탐색)를 사용해 해결하기에 가장 적합한 문제는?

1. 모든 경로 탐색
2. 그래프 사이클 탐지
3. 최단 경로 탐색
4. 위상 정렬

## Q5 (객관식 · 2점)

DFS 와 BFS 를 비교한 설명으로 옳은 것은?

1. DFS 는 스택(또는 재귀)으로, BFS 는 큐로 구현한다.
2. BFS 는 한 경로를 끝까지 따라갔다가 막히면 되돌아오는 백트래킹 방식이다.
3. DFS 는 시작 노드에서 가까운 노드부터 방문하므로 최단 거리 탐색에 유리하다.
4. BFS 로는 시작 노드와 이어진 노드를 모두 방문할 수 없다.

## Q6 (객관식 · 2점)

그래프에 사이클(몇 개의 엣지를 지나 출발한 노드로 돌아오는 길)이 있을 때, DFS 가 같은 노드를 끝없이 다시 탐색하지 않게 처리하는 방법은?

1. BFS 로 전환한다.
2. 방문한 노드를 기록하여 이미 방문한 노드는 탐색하지 않는다.
3. 사이클을 무시하고 탐색을 계속한다.
4. 재귀 깊이를 제한한다.

## Q7 (출력 예측 · 3점)

다음 코드의 출력 결과를 그대로 적으세요.

```python
graph1 = {1: [2, 3, 5], 2: [1, 3], 3: [1, 2, 4], 4: [3, 5], 5: [1, 4]}
print(len(graph1))
print(graph1[3])
print(len(graph1[1]))
print(graph1[4][1])
```

## Q8 (출력 예측 · 3점)

다음 코드의 출력 결과를 그대로 적으세요.

```python
graph = [[0, 1, 1], [0, 0, 1], [1, 0, 0], [1, 1, 0]]
print(len(graph), len(graph[0]))
print(graph[1][2], graph[2][1])
for row in graph:
    print(row)
```

## Q9 (객관식 · 2점)

노드가 1, 2, 3, 4, 5 이고 엣지가 `1→2`, `1→3`, `2→3`, `3→4`, `5→1`, `5→4` 인 **방향 그래프**가 있습니다.
키는 노드, 값은 그 노드에서 화살표 하나를 따라 바로 갈 수 있는 노드의 리스트로 두는 강의의 방식으로 이 그래프를 옳게 표현한 딕셔너리는?

1. `{1: [2, 3, 5], 2: [1, 3], 3: [1, 2, 4], 4: [3, 5], 5: [1, 4]}`
2. `{1: [2, 3], 2: [3], 3: [4], 4: [], 5: [1, 4]}`
3. `{1: [5], 2: [1], 3: [1, 2], 4: [3, 5], 5: []}`
4. `{1: [2, 3], 2: [3], 3: [4], 4: [5], 5: [1]}`

## Q10 (객관식 · 2점)

네 노드가 아래 그림처럼 사각형으로 이어진 그래프를 `my_dfs` 로 탐색합니다. 출력되는 방문 순서로 옳은 것은?

```
A - B
|   |
C - D
```

```python
def my_dfs(graph, start_node):
    stack = list()
    visited = list()
    stack.append(start_node)
    while stack:
        node = stack.pop()
        if node not in visited:
            stack.extend(reversed(graph[node]))
            visited.append(node)
    return visited

graph = {"A": ["B", "C"], "B": ["A", "D"], "C": ["A", "D"], "D": ["B", "C"]}
print(my_dfs(graph, "A"))
```

1. A → B → D → C
2. A → C → D → B
3. A → D → C → B
4. A → B → C → D

## Q11 (객관식 · 2점)

아래 지도에서 `□` 는 길, `■` 는 벽입니다. 길은 0, 벽은 1 로 두고 이 지도를 2차원 리스트로 옳게 옮긴 것은?

```
□ □ ■ □ ■
■ □ ■ □ □
□ □ ■ ■ □
□ ■ □ □ □
□ □ □ ■ ■
```

**1번**

```python
graph = [[1, 1, 0, 1, 0],
         [0, 1, 0, 1, 1],
         [1, 1, 0, 0, 1],
         [1, 0, 1, 1, 1],
         [1, 1, 1, 0, 0]]
```

**2번**

```python
graph = [[0, 1, 0, 0, 0],
         [0, 0, 0, 1, 0],
         [1, 1, 1, 0, 0],
         [0, 0, 1, 0, 1],
         [1, 0, 0, 0, 1]]
```

**3번**

```python
graph = [[0, 0, 1, 0, 1],
         [1, 0, 1, 0, 0],
         [0, 0, 1, 1, 0],
         [0, 1, 0, 0, 0],
         [0, 0, 0, 1, 1]]
```

**4번**

```python
graph = [[0, 0, 0, 1, 1],
         [0, 1, 0, 0, 0],
         [0, 0, 1, 1, 0],
         [1, 0, 1, 0, 0],
         [0, 0, 1, 0, 1]]
```

## Q12 (출력 예측 · 3점)

다음 코드의 출력 결과를 그대로 적으세요.

```python
stack = ["A"]
node = stack.pop()
stack.extend(reversed(["B", "C", "D"]))
print(stack)
print(stack.pop())
stack.append(["E", "F"])
stack.extend(["G", "H"])
print(len(stack), stack[-1])
```

## Q13 (출력 예측 · 3점)

다음 코드의 출력 결과를 그대로 적으세요.

```python
queue = [3, 1, 3, 2, 1]
visited = list()
count = 0
while queue:
    node = queue.pop(0)
    count += 1
    if node not in visited:
        visited.append(node)
print(visited)
print(count, queue)
```

## Q14 (출력 예측 · 3점)

다음 코드의 출력 결과를 그대로 적으세요. `print` 가 쉼표 자리에 넣는 공백까지 그대로 적어야 합니다.

```python
def my_bfs(graph, start_node):
    queue = list()
    visited = list()
    queue.append(start_node)
    while queue:
        node = queue.pop(0)
        if node not in visited:
            queue.extend(graph[node])
            visited.append(node)
    print("bfs - ", visited)
    return visited

graph = {1: [3, 2], 2: [1, 4], 3: [1, 4, 5], 4: [2, 3], 5: [3]}
result = my_bfs(graph, 1)
print(len(result), result[-1])
```

## Q15 (단답 · 3점)

다음 코드에서 `my_dfs(graph, "두")` 가 반환하는 리스트의 **6번째** 요소(6번째로 방문하는 노드)를 적으세요. 따옴표 없이 한 글자만 적습니다.

```python
def my_dfs(graph, start_node):
    stack = list()
    visited = list()
    stack.append(start_node)
    while stack:
        node = stack.pop()
        if node not in visited:
            stack.extend(reversed(graph[node]))
            visited.append(node)
    return visited

graph = {
    "두": ["산", "로", "키"],
    "산": ["두", "부"],
    "로": ["두"],
    "키": ["두", "트"],
    "부": ["산"],
    "트": ["키", "캠", "프"],
    "캠": ["트"],
    "프": ["트"],
}
```

## Q16 (단답 · 3점)

다음 코드에서 `my_bfs(graph, "두")` 가 반환하는 리스트의 **5번째** 요소(5번째로 방문하는 노드)를 적으세요. 따옴표 없이 한 글자만 적습니다.

```python
def my_bfs(graph, start_node):
    queue = list()
    visited = list()
    queue.append(start_node)
    while queue:
        node = queue.pop(0)
        if node not in visited:
            queue.extend(graph[node])
            visited.append(node)
    return visited

graph = {
    "두": ["산", "로", "키"],
    "산": ["두", "부"],
    "로": ["두"],
    "키": ["두", "트"],
    "부": ["산"],
    "트": ["키", "캠", "프"],
    "캠": ["트"],
    "프": ["트"],
}
```

## Q17 (객관식 · 2점)

다음 코드를 실행한 결과로 옳은 것은?

```python
def my_bfs(graph, start_node):
    queue = list()
    visited = list()
    queue.append(start_node)
    while queue:
        node = queue.pop(0)
        if node not in visited:
            queue.extend(graph[node])
            visited.append(node)
    return visited

graph = {1: [2, 3], 2: [3], 3: [4]}
print(my_bfs(graph, 1))
```

1. `[1, 2, 3, 4]` 가 출력된다.
2. `[1, 2, 3]` 이 출력된다.
3. `while` 문이 끝나지 않아 아무것도 출력되지 않는다.
4. 오류가 발생한다.

## Q18 (출력 예측 · 3점)

다음 코드의 출력 결과를 그대로 적으세요. 강의의 `my_dfs` 와 달리 인접 노드를 뒤집지 않고 스택에 넣습니다.

```python
def search(graph, start_node):
    stack = [start_node]
    visited = []
    while stack:
        node = stack.pop()
        if node not in visited:
            stack.extend(graph[node])
            visited.append(node)
    return visited

g1 = {1: [2, 3, 4], 2: [1, 5], 3: [1, 6], 4: [1, 6], 5: [2, 6], 6: [3, 4, 5]}
print(search(g1, 1))
print(search(g1, 5))
```

## Q19 (출력 예측 · 3점)

방향 그래프 `graph2` 를 탐색하는 다음 코드의 출력 결과를 그대로 적으세요.

```python
def my_dfs(graph, start_node):
    stack = [start_node]
    visited = []
    while stack:
        node = stack.pop()
        if node not in visited:
            stack.extend(reversed(graph[node]))
            visited.append(node)
    return visited

def my_bfs(graph, start_node):
    queue = [start_node]
    visited = []
    while queue:
        node = queue.pop(0)
        if node not in visited:
            queue.extend(graph[node])
            visited.append(node)
    return visited

graph2 = {1: [2, 3], 2: [3], 3: [4], 4: [], 5: [1, 4]}
print(my_dfs(graph2, 1))
print(my_dfs(graph2, 5))
print(my_bfs(graph2, 5))
```

## Q20 (출력 예측 · 3점)

다음 코드의 출력 결과를 그대로 적으세요. `dfs` 는 스택 대신 재귀 호출로 만든 깊이 우선 탐색입니다.

```python
def dfs(graph, node, visited):
    visited.append(node)
    for next_node in graph[node]:
        if next_node not in visited:
            dfs(graph, next_node, visited)
    return visited

graph = {
    "S": ["A", "B"],
    "A": ["S", "C", "D"],
    "B": ["S", "D"],
    "C": ["A"],
    "D": ["A", "B", "E"],
    "E": ["D"],
}
order = dfs(graph, "S", [])
print(order)
print(len(order), order[3])
```

## Q21 (단답 · 3점)

노드 집합 `V` 와 엣지 집합 `E` 가 아래처럼 주어진 무방향 그래프 `G = (V, E)` 에서 노드 `3` 의 차수(degree)를 숫자로 적으세요.

```
V = {1, 2, 3, 4, 5}
E = {(1, 2), (1, 3), (1, 5), (2, 3), (3, 4), (3, 5), (4, 5)}
```

## Q22 (객관식 · 2점)

DFS 와 BFS 의 영어 이름과 우리말 이름을 옳게 짝지은 것은?

1. DFS 는 Depth First Search(너비 우선 탐색), BFS 는 Breadth First Search(깊이 우선 탐색)
2. DFS 는 Data First Search(깊이 우선 탐색), BFS 는 Binary First Search(너비 우선 탐색)
3. DFS 는 Depth First Search(깊이 우선 탐색), BFS 는 Breadth First Search(너비 우선 탐색)
4. DFS 는 Down First Search(깊이 우선 탐색), BFS 는 Bottom First Search(너비 우선 탐색)

## Q23 (객관식 · 2점)

강의에서 설명한 DFS 의 동작 방식 (가)~(라)를 처음 실행되는 순서대로 나열한 것은? (가)와 (라)는 스택에 방문할 노드가 남지 않을 때까지 반복합니다.

- (가) 방문할 노드를 스택에서 하나 꺼낸다.
- (나) 탐색 시작 노드를 스택에 넣는다.
- (다) 방문할 노드를 담을 스택과, 방문한 노드를 기록할 리스트를 만든다.
- (라) 꺼낸 노드가 방문한 노드가 아니면 그 인접 노드를 스택에 넣고 방문 처리한다.

1. (나) → (다) → (가) → (라)
2. (다) → (나) → (가) → (라)
3. (다) → (가) → (나) → (라)
4. (다) → (나) → (라) → (가)

## Q24 (출력 예측 · 3점)

다음 코드의 출력 결과를 그대로 적으세요. `graph` 는 길이 0, 벽이 1 인 지도이고 위치는 `(행, 열)` 튜플입니다.

```python
graph = [
    [0, 0, 1],
    [1, 0, 0],
    [0, 0, 1],
]
moves = [(1, 0), (0, 1), (-1, 0), (0, -1)]
queue = [(0, 0)]
visited = []
while queue:
    node = queue.pop(0)
    if node not in visited:
        visited.append(node)
        for move in moves:
            nr = node[0] + move[0]
            nc = node[1] + move[1]
            if nr >= 0 and nr < 3 and nc >= 0 and nc < 3:
                if graph[nr][nc] == 0:
                    queue.append((nr, nc))
print(visited)
print(len(visited), visited[-1])
```

## Q25 (단답 · 3점)

너비 우선 탐색(BFS)은 방문할 노드를 넣은 순서대로 꺼내야 합니다. 이때 방문할 노드를 담아 두는 자료구조의 이름을 한글로 적으세요.
