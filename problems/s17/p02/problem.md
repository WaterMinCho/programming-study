# p02. DFS 함수 완성 (빈칸 채우기 · 4점)

딕셔너리로 표현한 그래프 `graph` 를 `start_node` 에서 시작해 깊이 우선 탐색(DFS)하고, 방문한 순서대로 노드를 담은 리스트를 반환하는 `my_dfs` 함수입니다.
빈칸(`____`) 3곳을 채워 함수를 완성하세요.

- 방문할 노드는 스택에 담고, 스택에서 하나씩 꺼내 방문합니다.
- 한 노드에서 갈 수 있는 노드가 여럿이면 리스트의 앞에 적힌 노드를 먼저 방문합니다. 스택은 마지막에 넣은 것이 먼저 나오므로 인접 노드의 순서를 뒤집어서 넣습니다.
- 이미 방문한 노드는 다시 방문하지 않습니다.
- 빈칸만 채웁니다. 다른 줄을 고치거나 줄을 추가하면 오답 처리됩니다.

```python
def my_dfs(graph, start_node):
    stack = list()
    visited = list()

    stack.append(start_node)

    while stack:
        node = stack.____()

        if node ____ visited:
            stack.extend(____(graph[node]))
            visited.append(node)

    return visited


my_graph = {
    "A": ["B", "C", "D"],
    "B": ["A", "E"],
    "C": ["A", "F", "G"],
    "D": ["A", "H"],
    "E": ["B", "I"],
    "F": ["C", "J"],
    "G": ["C"],
    "H": ["D"],
    "I": ["E"],
    "J": ["F"],
}
g1 = {1: [2, 3, 4], 2: [1, 5], 3: [1, 6], 4: [1, 6], 5: [2, 6], 6: [3, 4, 5]}
```

## 입출력 예

| 호출 | 반환값 |
|---|---|
| `my_dfs(my_graph, "A")` | `['A', 'B', 'E', 'I', 'C', 'F', 'J', 'G', 'D', 'H']` |
| `my_dfs(g1, 1)` | `[1, 2, 5, 6, 3, 4]` |
